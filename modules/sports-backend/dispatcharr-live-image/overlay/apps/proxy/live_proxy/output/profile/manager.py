"""
Output Profile Transcode Manager

Reads from the shared TS Redis buffer, pipes data through a user-defined
transcoding command (pipe:0 stdin → pipe:1 stdout), and writes the output
chunks to a Redis-backed StreamBuffer under:

    live:channel:{channel_id}:profile:{profile_id}:buffer:*

One transcode process runs per active (channel, profile) pair across the
entire cluster. The TS-owning worker starts the process; non-owning workers
create a read-only StreamBuffer pointing at the same Redis keys.
"""

import select
import threading
import time
import uuid
from core.utils import RedisClient
from ...input.buffer import StreamBuffer
from ...generation_authority import GenerationAuthority
from ...redis_keys import RedisKeys
from ...config_helper import ConfigHelper
from ...utils import get_logger

logger = get_logger()

PROFILE_STATE_ACTIVE = "active"
PROFILE_STATE_STOPPED = "stopped"

# Orphan backstop TTL; refreshed while the transcode is alive, deleted on stop.
PROFILE_KEY_TTL = 3600
PROFILE_TTL_REFRESH_INTERVAL = 60
PROFILE_OWNER_TTL = 180


class OutputProfileManager:
    """
    Reads the TS Redis buffer for a channel, transcodes via a user-supplied
    command, and writes output chunks into a profile-namespaced StreamBuffer.
    """

    def __init__(self, channel_id, profile_id, command, ts_buffer, worker_id):
        """
        Args:
            channel_id: Channel UUID string.
            profile_id: OutputProfile PK (int).
            command: List from OutputProfile.build_command().
            ts_buffer: Source StreamBuffer (the channel's raw TS input buffer).
            worker_id: This worker's ID string for owner-lock coordination.
        """
        self.channel_id = channel_id
        self.profile_id = profile_id
        self.command = command
        self.ts_buffer = ts_buffer
        self.worker_id = worker_id
        # A manager lifecycle needs its own identity even when a worker
        # replaces a stale profile process on the same host.
        self._owner_identity = f"{worker_id}:{uuid.uuid4().hex}"
        self.running = False
        self._process = None
        self._writer_thread = None
        self._reader_thread = None
        self._stderr_thread = None
        self._redis = RedisClient.get_client()
        self.output_buffer = None  # assigned in start()

        # Verified transform state. The raw source and transformed
        # destination deliberately use different authority scopes.
        self._source_authority = None
        self._source_epoch = None
        self._source_generation_id = None

        self._derived_authority = None
        self._derived_grant_token = None
        self._derived_grant_epoch = None
        self._derived_generation_id = None
        self._derived_authority_scope = (
            f"{self.channel_id}/profile/{self.profile_id}"
        )
        self._last_ttl_refresh = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _bind_verified_source_reader(self):
        """Bind TS input to the current verified raw generation."""
        redis_client = getattr(
            self.ts_buffer,
            "redis_client",
            None,
        )

        if redis_client is None:
            raise RuntimeError(
                "Verified profile input requires Redis."
            )

        authority = GenerationAuthority(redis_client)

        current = authority.current_generation(
            self.channel_id
        )

        if current is None:
            raise RuntimeError(
                "No verified raw generation for profile input."
            )

        epoch, generation_id = current

        self.ts_buffer.configure_verified_reader(
            authority=authority,
            grant_epoch=epoch,
            generation_id=generation_id,
        )

        self._source_authority = authority
        self._source_epoch = epoch
        self._source_generation_id = generation_id

    def _source_generation_is_current(self):
        if (
            self._source_authority is None
            or self._source_epoch is None
            or not self._source_generation_id
        ):
            return False

        try:
            current = self._source_authority.current_generation(
                self.channel_id
            )
        except Exception:
            return False

        return current == (
            self._source_epoch,
            self._source_generation_id,
        )

    def _bind_new_derived_generation(self):
        """Create a separate generation for transformed MPEG-TS."""
        if self.output_buffer is None:
            raise RuntimeError(
                "Profile output buffer is not available."
            )

        redis_client = getattr(
            self.output_buffer,
            "redis_client",
            None,
        )

        if redis_client is None:
            raise RuntimeError(
                "Verified profile output requires Redis."
            )

        # Renewal occurs from _refresh_redis_ttls(), which is
        # rate-limited to 60 seconds. Keep a >2x lease margin.
        authority = GenerationAuthority(
            redis_client,
            lease_seconds=180,
        )

        grant = authority.acquire(
            channel_id=self._derived_authority_scope,
            worker_id=self._owner_identity,
            owner_key=RedisKeys.output_owner(
                self.channel_id, f"mpegts:p{self.profile_id}"
            ),
        )

        generation_id = (
            f"{grant.epoch}-{uuid.uuid4().hex}"
        )

        try:
            authority.activate_generation(
                channel_id=self._derived_authority_scope,
                grant_token=grant.token,
                generation_id=generation_id,
            )

            self.output_buffer.activate_generation(
                generation_id
            )

            self.output_buffer.configure_verified_publication(
                authority=authority,
                grant_token=grant.token,
                generation_id=generation_id,
                authority_channel_id=(
                    self._derived_authority_scope
                ),
                owner_key=RedisKeys.output_owner(
                    self.channel_id, f"mpegts:p{self.profile_id}"
                ),
            )

        except Exception:
            try:
                authority.release(
                    channel_id=self._derived_authority_scope,
                    grant_token=grant.token,
                )
            except Exception:
                pass
            raise

        self._derived_authority = authority
        self._derived_grant_token = grant.token
        self._derived_grant_epoch = grant.epoch
        self._derived_generation_id = generation_id

    def _release_derived_generation(self):
        authority = self._derived_authority
        token = self._derived_grant_token

        if authority is None or not token:
            return False

        try:
            authority.release(
                channel_id=self._derived_authority_scope,
                grant_token=token,
            )
        except Exception:
            return False

        self._derived_grant_token = None

        if (
            self.output_buffer is not None
            and getattr(
                self.output_buffer,
                "_verified_mode",
                False,
            )
        ):
            with self.output_buffer.lock:
                self.output_buffer._verified_failed = True
                self.output_buffer._partial_packet = bytearray()
                self.output_buffer._write_buffer = bytearray()

        return True

    def _bind_existing_derived_reader(self):
        """Bind a non-owner profile buffer for verified reads only."""
        if self.output_buffer is None:
            return False

        redis_client = getattr(
            self.output_buffer,
            "redis_client",
            None,
        )

        if redis_client is None:
            return False

        authority = GenerationAuthority(
            redis_client,
            lease_seconds=180,
        )

        current = authority.current_generation(
            self._derived_authority_scope
        )

        if current is None:
            return False

        epoch, generation_id = current

        self.output_buffer.configure_verified_reader(
            authority=authority,
            grant_epoch=epoch,
            generation_id=generation_id,
            authority_channel_id=(
                self._derived_authority_scope
            ),
        )

        return True

    def start(self) -> bool:
        """
        Acquire the owner lock, spawn the transcode process and threads.
        Returns True if this worker started the process, False if another
        worker already owns it (caller should still use output_buffer for reads).
        """
        logger.debug(
            f"[Profile:{self.profile_id}:{self.channel_id[:8]}] start() called"
        )
        if not self._acquire_owner_lock():
            logger.info(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                "Another worker owns transcode, using shared buffer"
            )
            self.output_buffer = self._make_buffer()
            self._bind_existing_derived_reader()
            return False

        self.output_buffer = self._make_buffer()

        try:
            self._bind_verified_source_reader()
            self._bind_new_derived_generation()
        except Exception as e:
            logger.error(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                f"Verified generation binding failed: {e}",
                exc_info=True,
            )
            self._release_derived_generation()
            self._release_owner_lock()
            return False

        try:
            from ...utils import posix_spawn_proc
            self._process = posix_spawn_proc(self.command)
        except (FileNotFoundError, OSError) as e:
            logger.error(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                f"Failed to start transcode process: {e}"
            )
            self._release_derived_generation()
            self._release_owner_lock()
            return False

        self.running = True
        try:
            self._set_state(PROFILE_STATE_ACTIVE)
        except Exception:
            self.stop()
            return False

        short = f"{self.channel_id[:8]}:p{self.profile_id}"
        self._writer_thread = threading.Thread(
            target=self._writer_loop, daemon=True,
            name=f"profile-writer-{short}"
        )
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True,
            name=f"profile-reader-{short}"
        )
        self._stderr_thread = threading.Thread(
            target=self._stderr_loop, daemon=True,
            name=f"profile-stderr-{short}"
        )
        self._writer_thread.start()
        self._reader_thread.start()
        self._stderr_thread.start()

        logger.info(
            f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
            f"Transcode started (pid={self._process.pid})"
        )
        return True

    def stop(self):
        """Stop the transcode process and clean up all Redis keys."""
        if not self.running:
            return
        self.running = False
        logger.info(
            f"[Profile:{self.profile_id}:{self.channel_id[:8]}] Stopping transcode"
        )

        try:
            if self._process and self._process.stdin:
                self._process.stdin.close()
        except Exception:
            pass

        for t in (self._writer_thread, self._reader_thread):
            if t and t.is_alive():
                try:
                    t.join(timeout=5)
                except Exception:
                    pass

        try:
            if self._process and self._process.poll() is None:
                self._process.kill()
                self._process.wait(timeout=3)
        except Exception:
            pass

        self._cleanup_redis()
        logger.info(
            f"[Profile:{self.profile_id}:{self.channel_id[:8]}] Transcode stopped"
        )

    # ------------------------------------------------------------------
    # Internal threads
    # ------------------------------------------------------------------

    def _write_all(self, data: bytes):
        """Write all bytes to process stdin, looping on partial writes."""
        view = memoryview(data)
        offset = 0
        total = len(view)
        while offset < total:
            if not self.running:
                return
            n = self._process.stdin.write(view[offset:])
            if n is None:
                # Pipe full (EAGAIN on non-blocking FD); yield cooperatively
                select.select([], [self._process.stdin], [], 1.0)
            elif n <= 0:
                raise OSError("stdin write returned no bytes")
            else:
                offset += n

    def _writer_loop(self):
        """Read TS chunks from Redis and write to the transcode process stdin."""
        behind_seconds = ConfigHelper.new_client_behind_seconds()
        start_index = self.ts_buffer.find_chunk_index_by_time(behind_seconds) if behind_seconds > 0 else None
        if start_index is None:
            start_index = self.ts_buffer.index
        local_index = start_index
        logger.debug(
            f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
            f"Writer started at index {local_index}"
        )

        try:
            while self.running:
                if not self._source_generation_is_current():
                    logger.warning(
                        f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                        "Raw source generation changed; invalidating profile output"
                    )
                    self._release_derived_generation()
                    self.running = False
                    return

                indexed_chunks = (
                    self.ts_buffer
                    .get_indexed_chunks_for_active_generation(
                        start_index=local_index,
                        count=max(
                            1,
                            min(
                                20,
                                self.ts_buffer.index - local_index,
                            ),
                        ),
                    )
                )

                chunks = [
                    data
                    for _, data in indexed_chunks
                ]

                new_index = (
                    indexed_chunks[-1][0]
                    if indexed_chunks
                    else local_index
                )

                if chunks:
                    local_index = new_index
                    for chunk in chunks:
                        if not self.running:
                            break
                        try:
                            self._write_all(chunk)
                            self._process.stdin.flush()
                        except (BrokenPipeError, OSError) as e:
                            logger.warning(
                                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                                f"Stdin error: {e}"
                            )
                            self.running = False
                            return
                else:
                    if self.ts_buffer.index > local_index + 20:
                        local_index = self.ts_buffer.index - 5
                    time.sleep(0.05)

        except Exception as e:
            logger.error(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                f"Writer loop error: {e}", exc_info=True
            )
        finally:
            try:
                if self._process and self._process.stdin:
                    self._process.stdin.close()
            except Exception:
                pass
            logger.debug(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] Writer loop exited"
            )

    def _reader_loop(self):
        """Read chunks from process stdout and write to the output StreamBuffer."""
        read_size = 65536
        logger.debug(
            f"[Profile:{self.profile_id}:{self.channel_id[:8]}] Reader started"
        )

        try:
            while self.running:
                self._refresh_redis_ttls()
                ready, _, _ = select.select([self._process.stdout], [], [], 1.0)
                if not ready:
                    if self._process.poll() is not None:
                        logger.info(
                            f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                            f"Process exited (code={self._process.returncode})"
                        )
                        break
                    continue

                data = self._process.stdout.read(read_size)
                if not data:
                    logger.info(
                        f"[Profile:{self.profile_id}:{self.channel_id[:8]}] stdout EOF"
                    )
                    break

                if (
                    not self._derived_generation_id
                    or not self.output_buffer.add_chunk(
                        data,
                        generation_id=self._derived_generation_id,
                    )
                ):
                    logger.error(
                        f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                        "Verified derived publication rejected"
                    )
                    self._release_derived_generation()
                    self.running = False
                    break

        except Exception as e:
            logger.error(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                f"Reader loop error: {e}", exc_info=True
            )
        finally:
            if self.output_buffer:
                self.output_buffer.stop()
            logger.info(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] Reader loop exited"
            )

    def _stderr_loop(self):
        """Log process stderr at WARNING level."""
        import os as _os
        import select as _select
        try:
            stderr_fd = self._process.stderr.fileno()
            buf = b""
            while self.running:
                ready, _, _ = _select.select([stderr_fd], [], [], 1.0)
                if not ready:
                    if self._process.poll() is not None:
                        break
                    continue
                chunk = _os.read(stderr_fd, 4096)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line_bytes, buf = buf.split(b'\n', 1)
                    line = line_bytes.decode(errors="replace").rstrip()
                    if line:
                        logger.warning(
                            f"[Profile:{self.profile_id}:{self.channel_id[:8]}] {line}"
                        )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    def _make_buffer(self) -> StreamBuffer:
        """Create a StreamBuffer wired to this profile's Redis key namespace."""
        fmt = f"mpegts:p{self.profile_id}"
        return StreamBuffer(
            channel_id=self.channel_id,
            redis_client=RedisClient.get_buffer(),
            buffer_index_key=RedisKeys.output_buffer_index(self.channel_id, fmt),
            buffer_chunk_prefix=RedisKeys.output_buffer_chunk_prefix(self.channel_id, fmt),
            chunk_timestamps_key=RedisKeys.output_chunk_timestamps(self.channel_id, fmt),
        )

    def _acquire_owner_lock(self) -> bool:
        if not self._redis:
            return False
        owner_key = RedisKeys.output_owner(self.channel_id, f"mpegts:p{self.profile_id}")
        return bool(self._redis.set(owner_key, self._owner_identity, nx=True, ex=PROFILE_OWNER_TTL))

    def _release_owner_lock(self):
        if self._redis:
            try:
                self._redis.eval(
                    "if redis.call('GET', KEYS[1]) == ARGV[1] "
                    "then return redis.call('DEL', KEYS[1]) end return 0",
                    1, RedisKeys.output_owner(self.channel_id, f"mpegts:p{self.profile_id}"),
                    self._owner_identity,
                )
            except Exception:
                pass

    def _set_state(self, state: str):
        if not self._redis or not self._derived_authority or not self._derived_grant_token:
            raise RuntimeError("Profile owner state is unavailable.")
        fmt = f"mpegts:p{self.profile_id}"
        grant_key = self._derived_authority._keys(self._derived_authority_scope)[0]
        if self._redis.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] and "
            "redis.call('HGET', KEYS[3], 'token') == ARGV[2] "
            "then redis.call('SETEX', KEYS[2], tonumber(ARGV[3]), ARGV[4]); "
            "return 1 end return 0",
            3, RedisKeys.output_owner(self.channel_id, fmt),
            RedisKeys.output_state(self.channel_id, fmt), grant_key,
            self._owner_identity, self._derived_grant_token, PROFILE_KEY_TTL, state,
        ) != 1:
            raise RuntimeError("Profile owner state is stale.")

    def _refresh_redis_ttls(self):
        """Extend orphan-backstop TTLs while this transcode is alive.

        Rate-limited so long sessions keep owner/state without per-chunk Redis chatter.
        """
        now = time.time()
        if now - self._last_ttl_refresh < PROFILE_TTL_REFRESH_INTERVAL:
            return
        self._last_ttl_refresh = now
        if not self._redis or not self._derived_authority or not self._derived_grant_token:
            self.running = False
            self._release_derived_generation()
            return
        try:
            if (
                self._derived_authority is not None
                and self._derived_grant_token
                and self._derived_generation_id
            ):
                renewed = self._derived_authority.renew(
                    channel_id=self._derived_authority_scope,
                    grant_token=self._derived_grant_token,
                    generation_id=self._derived_generation_id,
                    owner_key=RedisKeys.output_owner(
                        self.channel_id, f"mpegts:p{self.profile_id}"
                    ),
                )

                if not renewed:
                    logger.error(
                        f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                        "Derived generation renewal failed"
                    )
                    self._release_derived_generation()
                    self.running = False
                    return

            fmt = f"mpegts:p{self.profile_id}"
            grant_key = self._derived_authority._keys(self._derived_authority_scope)[0]
            renewed_owner = self._redis.eval(
                "if redis.call('GET', KEYS[1]) ~= ARGV[1] or "
                "redis.call('HGET', KEYS[3], 'token') ~= ARGV[2] "
                "then return 0 end "
                "redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3])); "
                "redis.call('EXPIRE', KEYS[2], tonumber(ARGV[4])); return 1",
                3, RedisKeys.output_owner(self.channel_id, fmt),
                RedisKeys.output_state(self.channel_id, fmt), grant_key,
                self._owner_identity, self._derived_grant_token,
                PROFILE_OWNER_TTL, PROFILE_KEY_TTL,
            )
            if renewed_owner != 1:
                self.running = False
                self._release_derived_generation()
        except Exception as e:
            self.running = False
            self._release_derived_generation()
            logger.error(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                f"TTL refresh failed: {e}"
            )

    def _cleanup_redis(self):
        """Revoke only this writer; old media expires by TTL."""
        try:
            if self._redis and self._derived_grant_token and self._derived_authority:
                fmt = f"mpegts:p{self.profile_id}"
                grant_key = self._derived_authority._keys(self._derived_authority_scope)[0]
                self._redis.eval(
                    "if redis.call('GET', KEYS[1]) == ARGV[1] and "
                    "redis.call('HGET', KEYS[3], 'token') == ARGV[2] "
                    "then redis.call('DEL', KEYS[1], KEYS[2]); return 1 "
                    "end return 0",
                    3, RedisKeys.output_owner(self.channel_id, fmt),
                    RedisKeys.output_state(self.channel_id, fmt), grant_key,
                    self._owner_identity, self._derived_grant_token,
                )
        except Exception as e:
            logger.error(
                f"[Profile:{self.profile_id}:{self.channel_id[:8]}] "
                f"Redis cleanup error: {e}"
            )
        finally:
            self._release_derived_generation()
