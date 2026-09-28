"""Buffer management for TS streams"""

import threading
import time
import random
from ..redis_keys import RedisKeys
from ..config_helper import ConfigHelper
from ..constants import TS_PACKET_SIZE
from ..utils import get_logger
import gevent.event
import gevent

logger = get_logger()

class StreamBuffer:
    """Manages stream data buffering with optimized chunk storage"""

    def __init__(self, channel_id=None, redis_client=None,
                 buffer_index_key=None, buffer_chunk_prefix=None, chunk_timestamps_key=None):
        self.channel_id = channel_id
        self.redis_client = redis_client
        self.lock = threading.Lock()
        self.index = 0
        self.TS_PACKET_SIZE = TS_PACKET_SIZE

        self.buffer_index_key = buffer_index_key or (RedisKeys.buffer_index(channel_id) if channel_id else "")
        self.buffer_prefix = buffer_chunk_prefix or (RedisKeys.buffer_chunk_prefix(channel_id) if channel_id else "")

        self.chunk_ttl = ConfigHelper.redis_chunk_ttl()

        # Initialize from Redis if available
        if self.redis_client and channel_id:
            try:
                current_index = self.redis_client.get(self.buffer_index_key)
                if current_index:
                    self.index = int(current_index)
                    logger.info(f"Initialized buffer from Redis with index {self.index}")
            except Exception as e:
                logger.error(f"Error initializing buffer from Redis: {e}")

        self._write_buffer = bytearray()
        self.target_chunk_size = ConfigHelper.get('BUFFER_CHUNK_SIZE', TS_PACKET_SIZE * 5644)  # ~1MB default

        # Sorted-set key for chunk receive-timestamps (time-based positioning)
        self.chunk_timestamps_key = chunk_timestamps_key or (RedisKeys.chunk_timestamps(channel_id) if channel_id else "")

        # Register Lua scripts once — subsequent calls use EVALSHA (just the
        # SHA hash) instead of sending the full script text on every invocation.
        if self.redis_client:
            self._find_oldest_chunk_sha = self.redis_client.register_script(
                self._FIND_OLDEST_CHUNK_LUA
            )
            self._find_chunk_by_time_sha = self.redis_client.register_script(
                self._FIND_CHUNK_BY_TIME_LUA
            )
        else:
            self._find_oldest_chunk_sha = None
            self._find_chunk_by_time_sha = None

        # Track timers for proper cleanup
        self.stopping = False
        self.fill_timers = []
        self.chunk_available = gevent.event.Event()

    def configure_verified_reader(
        self,
        *,
        authority,
        grant_epoch,
        generation_id,
        authority_channel_id=None,
    ):
        """Bind a reader to an active epoch/generation.

        Reader bindings never contain the writer grant token and
        cannot authorize publication.
        """
        if authority is None:
            raise ValueError(
                "Verified reader requires authority."
            )

        if (
            isinstance(grant_epoch, bool)
            or not isinstance(grant_epoch, int)
            or grant_epoch <= 0
        ):
            raise ValueError("Invalid reader grant epoch.")

        if (
            not isinstance(generation_id, str)
            or not generation_id
            or generation_id != generation_id.strip()
        ):
            raise ValueError("Invalid reader generation ID.")

        with self.lock:
            self._verified_reader_authority = authority
            self._verified_reader_epoch = grant_epoch
            self._verified_reader_generation_id = generation_id
            self._verified_reader_authority_channel_id = (
                authority_channel_id or self.channel_id
            )

    def get_indexed_chunks_for_active_generation(
        self,
        *,
        start_index,
        count,
    ):
        """Return ``(original_index, bytes)`` for active verified media.

        Missing, expired, old-generation, or superseded-epoch chunks
        are omitted without renumbering surviving chunks.
        """
        if (
            isinstance(start_index, bool)
            or not isinstance(start_index, int)
            or start_index < 0
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            raise ValueError(
                "Invalid verified reader index range."
            )

        with self.lock:
            authority = getattr(
                self,
                "_verified_reader_authority",
                None,
            )
            grant_epoch = getattr(
                self,
                "_verified_reader_epoch",
                None,
            )
            generation_id = getattr(
                self,
                "_verified_reader_generation_id",
                None,
            )

            if (
                authority is None
                or grant_epoch is None
                or generation_id is None
            ):
                raise ValueError(
                    "No verified reader binding."
                )

            if not self.redis_client:
                raise RuntimeError(
                    "Verified retrieval requires Redis."
                )

            current_index = int(
                self.redis_client.get(
                    self.buffer_index_key
                )
                or 0
            )

            last_index = min(
                start_index + count,
                current_index,
            )

            indexed_chunks = []

            for index in range(
                start_index + 1,
                last_index + 1,
            ):
                data = (
                    authority
                    .read_buffer_chunk_for_active_generation(
                        channel_id=getattr(
                            self,
                            "_verified_reader_authority_channel_id",
                            self.channel_id,
                        ),
                        grant_epoch=grant_epoch,
                        generation_id=generation_id,
                        buffer_chunk_prefix=self.buffer_prefix,
                        chunk_index=index,
                    )
                )

                if data is not None:
                    indexed_chunks.append(
                        (index, data)
                    )

            return indexed_chunks

    def configure_verified_publication(
        self,
        *,
        authority,
        grant_token,
        generation_id,
        authority_channel_id=None,
        owner_key=None,
    ):
        """Configure the staged verified writer.

        Only a future trusted worker-lifecycle integration may call
        this method. Configuration itself does not attest ownership.
        """
        if authority is None:
            raise ValueError("Verified publication requires authority.")
        if not isinstance(grant_token, str) or not grant_token.strip():
            raise ValueError("Invalid grant token.")
        if not isinstance(generation_id, str) or not generation_id.strip():
            raise ValueError("Invalid generation ID.")
        if not isinstance(owner_key, str) or not owner_key.strip():
            raise ValueError("Verified publication requires a legacy owner key.")

        with self.lock:
            if getattr(self, "_active_generation", None) != generation_id:
                raise ValueError("Activate the generation before binding.")

            # A verified buffer must never become a legacy writer,
            # even when its authority binding is subsequently lost.
            self._verified_mode = True

            # An explicit trusted rebind discards any media that was
            # accumulated under a previous or failed binding.
            self._partial_packet = bytearray()
            self._write_buffer = bytearray()

            self._verified_authority = authority
            self._verified_grant_token = grant_token
            self._verified_generation_id = generation_id
            self._verified_authority_channel_id = (
                authority_channel_id or self.channel_id
            )
            self._verified_owner_key = owner_key
            self._verified_failed = False
            self._verified_reservation_activation = None
            self._verified_reservation_activated = False

    def require_verified_reservation_activation(self, callback, generation_id):
        """Bind a pending reservation to the first published raw TS chunk.

        Callback failure fences this writer. No viewer can use the reservation
        until its exact raw chunk and authority grant have been attested.
        """
        if not callable(callback):
            raise ValueError("Reservation activation callback is required")
        with self.lock:
            if (not getattr(self, "_verified_mode", False)
                or getattr(self, "_verified_failed", False)
                or generation_id != getattr(self, "_verified_generation_id", None)):
                raise ValueError("Verified generation binding changed")
            self._verified_reservation_activation = callback
            self._verified_reservation_activated = False
            self._verified_reservation_required = True

    def get_indexed_chunks_for_generation(
        self, *, start_index, count, grant_token, generation_id
    ):
        """Return original Redis indexes paired with verified bytes.

        This method is not wired into the viewer generators.
        Missing or rejected chunks are omitted WITHOUT renumbering.
        """
        if (
            not isinstance(start_index, int)
            or isinstance(start_index, bool)
            or start_index < 0
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
        ):
            raise ValueError("Invalid requested index range.")

        with self.lock:
            authority = getattr(self, "_verified_authority", None)
            if (
                authority is None
                or grant_token != getattr(
                    self, "_verified_grant_token", None
                )
                or generation_id != getattr(
                    self, "_verified_generation_id", None
                )
                or generation_id != getattr(
                    self, "_active_generation", None
                )
            ):
                raise ValueError("No matching verified buffer binding.")

            if not self.redis_client:
                raise RuntimeError("Verified retrieval requires Redis.")

            current_index = int(
                self.redis_client.get(self.buffer_index_key) or 0
            )
            last_index = min(start_index + count, current_index)

            indexed_chunks = []
            for index in range(start_index + 1, last_index + 1):
                data = authority.read_buffer_chunk_for_generation(
                    channel_id=self.channel_id,
                    grant_token=grant_token,
                    generation_id=generation_id,
                    buffer_chunk_prefix=self.buffer_prefix,
                    chunk_index=index,
                )
                if data is not None:
                    indexed_chunks.append((index, data))

            return indexed_chunks

    def activate_generation(self, generation_id):
        """Switch local producers without mixing pending media.

        This is local fencing only. It does not fence Redis writes across
        workers or invalidate chunks already published to Redis.
        """
        if (
            not isinstance(generation_id, str)
            or not generation_id
            or generation_id != generation_id.strip()
        ):
            raise ValueError("Invalid upstream generation ID.")

        with self.lock:
            if getattr(self, "_active_generation", None) == generation_id:
                return

            self._partial_packet = bytearray()
            self._write_buffer = bytearray()
            self._active_generation = generation_id

            if getattr(self, "_verified_mode", False):
                # A new generation must acquire its own binding.
                # Missing authority must not enable legacy writes.
                self._verified_authority = None
                self._verified_grant_token = None
                self._verified_generation_id = None
                self._verified_failed = True

    def add_chunk(self, chunk, *, generation_id=None):
        """Add data with optimized Redis storage and TS packet alignment"""
        if not chunk or self.stopping:
            return False

        try:
            # Accumulate partial packets between chunks
            if not hasattr(self, '_partial_packet'):
                self._partial_packet = bytearray()

            # Lock the full operation to prevent race with reset_buffer_position
            writes_done = 0
            with self.lock:
                if getattr(self, "_verified_mode", False):
                    if (
                        getattr(self, "_verified_failed", False)
                        or getattr(
                            self, "_verified_authority", None
                        ) is None
                        or not getattr(
                            self, "_verified_grant_token", None
                        )
                        or generation_id != getattr(
                            self, "_verified_generation_id", None
                        )
                    ):
                        return False

                if (
                    not isinstance(generation_id, str)
                    or not generation_id
                    or generation_id != getattr(
                        self, "_active_generation", None
                    )
                ):
                    return False

                # Combine with any previous partial packet
                combined_data = bytearray(self._partial_packet) + bytearray(chunk)

                # Calculate complete packets
                complete_packets_size = (len(combined_data) // self.TS_PACKET_SIZE) * self.TS_PACKET_SIZE

                if complete_packets_size == 0:
                    # Not enough data for a complete packet
                    self._partial_packet = combined_data
                    return True

                # Split into complete packets and remainder
                complete_packets = combined_data[:complete_packets_size]
                self._partial_packet = combined_data[complete_packets_size:]

                # Add completed packets to write buffer
                self._write_buffer.extend(complete_packets)

                # Only write to Redis when we have enough data for an optimized chunk
                while len(self._write_buffer) >= self.target_chunk_size:
                    # Extract a full chunk
                    chunk_data = self._write_buffer[:self.target_chunk_size]
                    self._write_buffer = self._write_buffer[self.target_chunk_size:]

                    # Verified mode replaces, rather than duplicates,
                    # the legacy Redis media publication.
                    authority = getattr(
                        self, "_verified_authority", None
                    )
                    if getattr(self, "_verified_mode", False):
                        if authority is None:
                            self._verified_failed = True
                            self._partial_packet = bytearray()
                            self._write_buffer = bytearray()
                            return False
                        if (
                            not self.redis_client
                            or generation_id != getattr(
                                self, "_verified_generation_id", None
                            )
                            or (getattr(self,
                                    "_verified_reservation_required", False)
                                and getattr(self,
                                    "_verified_reservation_activation", None)
                                    is None)
                        ):
                            self._verified_failed = True
                            self._partial_packet = bytearray()
                            self._write_buffer = bytearray()
                            return False

                        try:
                            chunk_index = authority.publish_buffer_chunk(
                                channel_id=getattr(
                                    self,
                                    "_verified_authority_channel_id",
                                    self.channel_id,
                                ),
                                grant_token=self._verified_grant_token,
                                generation_id=generation_id,
                                buffer_index_key=self.buffer_index_key,
                                buffer_chunk_prefix=self.buffer_prefix,
                                chunk=bytes(chunk_data),
                                chunk_ttl=self.chunk_ttl,
                                owner_key=getattr(self, "_verified_owner_key", None),
                            )
                        except Exception:
                            # Redis may have rejected the write, or
                            # accepted it before the response was lost.
                            # Do not retry these pending media bytes.
                            self._verified_failed = True
                            self._partial_packet = bytearray()
                            self._write_buffer = bytearray()
                            logger.warning(
                                "Verified buffer publication rejected"
                            )
                            return False

                        self.index = chunk_index
                        activation = getattr(
                            self, "_verified_reservation_activation", None
                        )
                        if (activation is not None
                            and not getattr(self,
                                "_verified_reservation_activated", False)):
                            try:
                                if activation(chunk_index) is not True:
                                    raise RuntimeError("Reservation activation rejected")
                            except Exception:
                                self._verified_failed = True
                                self._partial_packet = bytearray()
                                self._write_buffer = bytearray()
                                logger.warning(
                                    "Verified reservation activation rejected"
                                )
                                return False
                            self._verified_reservation_activated = True
                        writes_done += 1

                    elif self.redis_client:
                        # Legacy compatibility path: NOT verified.
                        chunk_index = self.redis_client.incr(
                            self.buffer_index_key
                        )
                        chunk_key = (
                            f"{self.buffer_prefix}{chunk_index}"
                        )

                        pipe = self.redis_client.pipeline(
                            transaction=False
                        )
                        pipe.setex(
                            chunk_key,
                            self.chunk_ttl,
                            bytes(chunk_data),
                        )

                        if self.chunk_timestamps_key:
                            now = time.time()
                            pipe.zadd(
                                self.chunk_timestamps_key,
                                {str(chunk_index): now},
                            )
                            pipe.zremrangebyscore(
                                self.chunk_timestamps_key,
                                '-inf',
                                now - self.chunk_ttl,
                            )
                            pipe.expire(
                                self.chunk_timestamps_key,
                                self.chunk_ttl,
                            )

                        pipe.execute()
                        self.index = chunk_index
                        writes_done += 1

            if writes_done > 0:
                logger.debug(f"Added {writes_done} chunks ({self.target_chunk_size} bytes each) to Redis for channel {self.channel_id} at index {self.index}")

            self.chunk_available.set()  # Signal that new data is available
            self.chunk_available.clear()  # Reset for next notification

            return True

        except Exception as e:
            logger.error(f"Error adding chunk to buffer: {e}")
            return False

    def reset_buffer_position(self):
        """
        Reset internal buffers for a clean stream transition (failover).

        Called by stream_manager.update_url() when switching between FFmpeg
        processes. Without this, _partial_packet from the old FFmpeg gets
        concatenated with the first bytes from the new FFmpeg, creating
        corrupted TS packets that break audio decoder sync in the client.
        """
        try:
            with self.lock:
                old_write_size = len(self._write_buffer)
                old_partial_size = len(getattr(self, '_partial_packet', b''))

                self._write_buffer = bytearray()
                if hasattr(self, '_partial_packet'):
                    self._partial_packet = bytearray()

                if old_write_size > 0 or old_partial_size > 0:
                    logger.info(
                        f"Reset buffer position for channel {self.channel_id}: "
                        f"cleared {old_write_size} bytes from write buffer, "
                        f"{old_partial_size} bytes from partial packet"
                    )
                else:
                    logger.debug(
                        f"Reset buffer position for channel {self.channel_id}: "
                        f"buffers were already clean"
                    )
        except Exception as e:
            logger.error(
                f"Error resetting buffer position for channel {self.channel_id}: {e}"
            )

    def get_chunks(self, start_index=None):
        """Get chunks from the buffer with detailed logging"""
        try:
            request_id = f"req_{random.randint(1000, 9999)}"
            logger.debug(f"[{request_id}] get_chunks called with start_index={start_index}")

            if not self.redis_client:
                logger.error("Redis not available, cannot retrieve chunks")
                return []

            # If no start_index provided, use most recent chunks
            if start_index is None:
                start_index = max(0, self.index - 10)  # Start closer to current position
                logger.debug(f"[{request_id}] No start_index provided, using {start_index}")

            # Get current index from Redis
            current_index = int(self.redis_client.get(self.buffer_index_key) or 0)

            # Calculate range of chunks to retrieve
            start_id = start_index + 1
            chunks_behind = current_index - start_id

            # Adaptive chunk retrieval based on how far behind
            if chunks_behind > 100:
                fetch_count = 15
                logger.debug(f"[{request_id}] Client very behind ({chunks_behind} chunks), fetching {fetch_count}")
            elif chunks_behind > 50:
                fetch_count = 10
                logger.debug(f"[{request_id}] Client moderately behind ({chunks_behind} chunks), fetching {fetch_count}")
            elif chunks_behind > 20:
                fetch_count = 5
                logger.debug(f"[{request_id}] Client slightly behind ({chunks_behind} chunks), fetching {fetch_count}")
            else:
                fetch_count = 3
                logger.debug(f"[{request_id}] Client up-to-date (only {chunks_behind} chunks behind), fetching {fetch_count}")

            end_id = min(current_index + 1, start_id + fetch_count)

            if start_id >= end_id:
                logger.debug(f"[{request_id}] No new chunks to fetch (start_id={start_id}, end_id={end_id})")
                return []

            # Log the range we're retrieving
            logger.debug(f"[{request_id}] Retrieving chunks {start_id} to {end_id-1} (total: {end_id-start_id})")

            # Directly fetch from Redis using pipeline for efficiency
            pipe = self.redis_client.pipeline()
            for idx in range(start_id, end_id):
                chunk_key = f"{self.buffer_prefix}{idx}"
                pipe.get(chunk_key)

            results = pipe.execute()

            # Process results
            chunks = [result for result in results if result is not None]

            # Count non-None results
            found_chunks = len(chunks)
            missing_chunks = len(results) - found_chunks

            if missing_chunks > 0:
                logger.debug(f"[{request_id}] Missing {missing_chunks}/{len(results)} chunks in Redis")

            # Update local tracking
            if chunks:
                self.index = end_id - 1

            # Final log message
            chunk_sizes = [len(c) for c in chunks]
            total_bytes = sum(chunk_sizes) if chunks else 0
            logger.debug(f"[{request_id}] Returning {len(chunks)} chunks ({total_bytes} bytes)")

            return chunks

        except Exception as e:
            logger.error(f"Error getting chunks from buffer: {e}", exc_info=True)
            return []

    def get_chunks_exact(self, start_index, count):
        """Get exactly the requested number of chunks from given index"""
        try:
            if not self.redis_client:
                logger.error("Redis not available, cannot retrieve chunks")
                return []

            # Calculate range to retrieve
            start_id = start_index + 1
            end_id = start_id + count

            # Get current buffer position
            current_index = int(self.redis_client.get(self.buffer_index_key) or 0)

            # If requesting beyond current buffer, return what we have
            if start_id > current_index:
                return []

            # Cap end at current buffer position
            end_id = min(end_id, current_index + 1)

            # Directly fetch from Redis using pipeline
            pipe = self.redis_client.pipeline()
            for idx in range(start_id, end_id):
                chunk_key = f"{self.buffer_prefix}{idx}"
                pipe.get(chunk_key)

            results = pipe.execute()

            # Filter out None results
            chunks = [result for result in results if result is not None]

            # Update local index if needed
            if chunks and start_id + len(chunks) - 1 > self.index:
                self.index = start_id + len(chunks) - 1

            return chunks

        except Exception as e:
            logger.error(f"Error getting exact chunks: {e}", exc_info=True)
            return []

    def stop(self):
        """Stop the buffer and cancel all timers"""
        # Set stopping flag first to prevent new timer creation
        self.stopping = True

        # Cancel all pending timers
        timers_cancelled = 0
        for timer in list(self.fill_timers):
            try:
                if timer and not timer.dead:  # Changed from timer.is_alive()
                    timer.kill()  # Changed from timer.cancel()
                    timers_cancelled += 1
            except Exception as e:
                logger.error(f"Error canceling timer: {e}")

        if timers_cancelled:
            logger.info(f"Cancelled {timers_cancelled} buffer timers for channel {self.channel_id}")

        # Clear timer list
        self.fill_timers.clear()

        try:
            with self.lock:
                if hasattr(self, '_write_buffer') and len(self._write_buffer) > 0:
                    discarded = len(self._write_buffer)
                    self._write_buffer = bytearray()
                    if hasattr(self, '_partial_packet'):
                        self._partial_packet = bytearray()
                    logger.debug(
                        f"Discarded {discarded} bytes from local write buffer "
                        f"for channel {self.channel_id}"
                    )
        except Exception as e:
            logger.error(f"Error during buffer stop: {e}")

    def get_optimized_client_data(self, client_index):
        """Get optimal amount of data for client streaming based on position and target size"""
        # Define limits
        MIN_CHUNKS = 3                      # Minimum chunks to read for efficiency
        MAX_CHUNKS = 20                     # Safety limit to prevent memory spikes
        TARGET_SIZE = 1024 * 1024           # Target ~1MB per response (typical media buffer)
        MAX_SIZE = 2 * 1024 * 1024          # Hard cap at 2MB

        # Calculate how far behind we are
        chunks_behind = self.index - client_index

        # Determine optimal chunk count
        if chunks_behind <= MIN_CHUNKS:
            # Not much data, retrieve what's available
            chunk_count = max(1, chunks_behind)
        elif chunks_behind <= MAX_CHUNKS:
            # Reasonable amount behind, catch up completely
            chunk_count = chunks_behind
        else:
            # Way behind, retrieve MAX_CHUNKS to avoid memory pressure
            chunk_count = MAX_CHUNKS

        # Retrieve chunks
        chunks = self.get_chunks_exact(client_index, chunk_count)

        # Check if we got significantly fewer chunks than expected (likely due to expiration)
        # Only check if we expected multiple chunks and got none or very few
        if chunk_count > 3 and len(chunks) == 0 and chunks_behind > 10:
            # Chunks are missing - likely expired from Redis
            # Return empty list to signal client should skip forward
            logger.debug(f"Chunks missing for client at index {client_index}, buffer at {self.index} ({chunks_behind} behind)")
            return [], client_index

        # Check total size
        total_size = sum(len(c) for c in chunks)

        # If we're under target and have more chunks available, get more
        if total_size < TARGET_SIZE and chunks_behind > chunk_count:
            # Calculate how many more chunks we can get
            additional = min(MAX_CHUNKS - chunk_count, chunks_behind - chunk_count)
            more_chunks = self.get_chunks_exact(client_index + chunk_count, additional)

            # Check if adding more would exceed MAX_SIZE
            additional_size = sum(len(c) for c in more_chunks)
            if total_size + additional_size <= MAX_SIZE:
                chunks.extend(more_chunks)
                chunk_count += len(more_chunks)

        return chunks, client_index + chunk_count

    # Lua script that runs an atomic binary search on the Redis server.
    # Chunks expire in FIFO order (same TTL, sequential writes), so the
    # alive range is contiguous: [oldest_surviving .. buffer_head].
    # Binary search finds the boundary in O(log N) EXISTS calls with zero
    # round-trips between steps and no TOCTOU races (Lua scripts are atomic).
    #
    # ARGV[1] = key prefix  (e.g. "live:channel:<id>:input:buffer:chunk:")
    # ARGV[2] = low index   (client_index + 1, first chunk the client needs)
    # ARGV[3] = high index  (buffer head, most recent chunk)
    #
    # Returns: the index of the oldest existing chunk, or -1 if none exist.
    _FIND_OLDEST_CHUNK_LUA = """
    local prefix = ARGV[1]
    local low    = tonumber(ARGV[2])
    local high   = tonumber(ARGV[3])

    if redis.call('EXISTS', prefix .. high) == 0 then
        return -1
    end

    local result = high
    while low <= high do
        local mid = math.floor((low + high) / 2)
        if redis.call('EXISTS', prefix .. mid) == 1 then
            result = mid
            high = mid - 1
        else
            low = mid + 1
        end
    end
    return result
    """

    def find_oldest_available_chunk(self, client_index):
        """Find the oldest (lowest-index) chunk that still exists in Redis.

        Executes an atomic Lua binary search on the Redis server — one
        round-trip, ~log2(N) EXISTS calls, no TOCTOU between steps.

        The actual read attempt (get_optimized_client_data) is what
        authoritatively detects expiration; this method is best-effort
        positioning that self-corrects on the next iteration if the found
        chunk also expires before the client can read it.

        Args:
            client_index: The client's current local_index (last consumed chunk).

        Returns:
            int or None: The local_index value the client should jump to
                         (one before the first available chunk), or None if no
                         chunks are available at all.
        """
        if not self.redis_client:
            return None

        low = client_index + 1   # First chunk the client needs
        high = self.index        # Latest chunk written

        if low > high:
            return None

        try:
            # Uses EVALSHA under the hood — sends only the SHA hash,
            # not the full script text, on every call after the first.
            result = self._find_oldest_chunk_sha(
                args=[
                    self.buffer_prefix,
                    low,
                    high,
                ],
            )

            if result == -1:
                return None

            # Return result - 1 so local_index points to one before the
            # first available chunk (matching the "last consumed" convention).
            return int(result) - 1

        except Exception as e:
            logger.error(f"Error running find_oldest_chunk Lua script for channel {self.channel_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # Lua script: atomic reverse-scan of the chunk_timestamps sorted set.
    # Finds the chunk whose receive-timestamp is closest to (but <=) a
    # target wall-clock time.  Returns the chunk index or -1.
    #
    # KEYS[1] = chunk_timestamps sorted-set key
    # ARGV[1] = target timestamp  (time.time() - desired_seconds_behind)
    # ------------------------------------------------------------------
    _FIND_CHUNK_BY_TIME_LUA = """
    local ts_key  = KEYS[1]
    local target  = tonumber(ARGV[1])

    -- ZREVRANGEBYSCORE returns members with score <= target, highest first.
    local result = redis.call('ZREVRANGEBYSCORE', ts_key, target, '-inf', 'LIMIT', 0, 1)
    if #result == 0 then
        return -1
    end
    return tonumber(result[1])
    """

    def find_chunk_index_by_time(self, seconds_behind):
        """Find the chunk index that was received approximately *seconds_behind*
        seconds ago.

        Uses an atomic Lua script against the chunk_timestamps sorted set so
        no data can expire between the lookup and the read.

        Returns:
            int or None: The chunk index to position the client at (this is
                         the *last consumed* convention, so the next read
                         starts at index+1).  None if no suitable chunk
                         exists.
        """
        if not self.redis_client or not self.chunk_timestamps_key:
            return None

        target_time = time.time() - seconds_behind

        try:
            result = self._find_chunk_by_time_sha(
                keys=[self.chunk_timestamps_key],
                args=[target_time],
            )
            if result is None or int(result) == -1:
                # No chunk old enough — fall back to the oldest available chunk
                oldest = self.redis_client.zrange(self.chunk_timestamps_key, 0, 0)
                if oldest:
                    return max(0, int(oldest[0]) - 1)  # "last consumed" convention
                return None

            # Return index - 1 so next read starts at that chunk
            return max(0, int(result) - 1)

        except Exception as e:
            logger.error(f"Error in find_chunk_index_by_time for channel {self.channel_id}: {e}")
            return None

    def schedule_timer(self, delay, callback, *args, **kwargs):
        """Schedule a timer and track it for proper cleanup"""
        if self.stopping:
            return None

        timer = gevent.spawn_later(delay, callback, *args, **kwargs)
        self.fill_timers.append(timer)
        return timer
