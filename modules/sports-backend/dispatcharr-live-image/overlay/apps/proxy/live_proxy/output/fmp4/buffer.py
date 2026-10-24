"""fMP4 buffer management - mirrors StreamBuffer but without TS packet alignment."""

import threading
import time
import gevent.event
from ...redis_keys import RedisKeys
from ...config_helper import ConfigHelper
from ...utils import get_logger

logger = get_logger()


class FMP4StreamBuffer:
    """
    Redis-backed buffer for fMP4 remux output.

    Functionally identical to StreamBuffer except:
    - Uses the fmp4:buffer:* Redis keyspace
    - No 188-byte TS packet alignment (raw byte accumulation)
    """

    def __init__(self, channel_id, redis_client=None, fmt='fmp4'):
        self.channel_id = channel_id
        self.redis_client = redis_client
        self.fmt = fmt
        self.lock = threading.Lock()
        self.index = 0

        self.buffer_index_key = RedisKeys.output_buffer_index(channel_id, fmt)
        self.buffer_prefix = RedisKeys.output_buffer_chunk_prefix(channel_id, fmt)
        self.chunk_timestamps_key = RedisKeys.output_chunk_timestamps(channel_id, fmt)
        self.chunk_ttl = ConfigHelper.redis_chunk_ttl()
        self.stopping = False
        self._verified_authority = None
        self._verified_token = None
        self._verified_epoch = None
        self._verified_generation = None
        self._verified_scope = None
        self._verified_failed = False
        self._init_published = False

        if self.redis_client and channel_id:
            try:
                current_index = self.redis_client.get(self.buffer_index_key)
                if current_index:
                    self.index = int(current_index)
            except Exception as e:
                logger.error(f"[fMP4Buffer:{channel_id}] Error initialising from Redis: {e}")

        self.chunk_available = gevent.event.Event()

        # Lua script for time-based start positioning (same as StreamBuffer)
        _LUA = """
        local ts_key = KEYS[1]
        local target = tonumber(ARGV[1])
        local result = redis.call('ZREVRANGEBYSCORE', ts_key, target, '-inf', 'LIMIT', 0, 1)
        if #result == 0 then return -1 end
        return tonumber(result[1])
        """
        if self.redis_client:
            try:
                self._find_chunk_by_time_sha = self.redis_client.register_script(_LUA)
            except Exception:
                self._find_chunk_by_time_sha = None
        else:
            self._find_chunk_by_time_sha = None

    def configure_verified_publication(self, *, authority, grant_token,
                                       generation_id, authority_channel_id,
                                       owner_key=None):
        if not isinstance(owner_key, str) or not owner_key.strip():
            raise ValueError("Verified fMP4 publication requires an owner key.")
        with self.lock:
            self._verified_authority = authority
            self._verified_token = grant_token
            self._verified_generation = generation_id
            self._verified_scope = authority_channel_id
            self._verified_owner_key = owner_key
            self._verified_failed = False
            self._init_published = False

    def configure_verified_reader(self, *, authority, grant_epoch,
                                  generation_id, authority_channel_id):
        with self.lock:
            self._verified_authority = authority
            self._verified_epoch = grant_epoch
            self._verified_generation = generation_id
            self._verified_scope = authority_channel_id

    def invalidate(self):
        with self.lock:
            self._verified_failed = True

    @property
    def _init_index_key(self):
        return RedisKeys.output_init(self.channel_id, self.fmt) + ":verified:index"

    @property
    def _init_chunk_prefix(self):
        return RedisKeys.output_init(self.channel_id, self.fmt) + ":verified:chunk:"

    def put_init(self, data: bytes) -> bool:
        """Publish init under the same authority as the media fragments."""
        with self.lock:
            if (self._verified_failed or self._verified_authority is None
                    or not self._verified_token or not self._verified_generation):
                return False
            try:
                self._verified_authority.publish_buffer_chunk(
                    channel_id=self._verified_scope,
                    grant_token=self._verified_token,
                    generation_id=self._verified_generation,
                    buffer_index_key=self._init_index_key,
                    buffer_chunk_prefix=self._init_chunk_prefix,
                    chunk=data,
                    chunk_ttl=max(self.chunk_ttl, 3600),
                    owner_key=self._verified_owner_key,
                )
                self._init_published = True
                return True
            except Exception:
                self._verified_failed = True
                return False

    def refresh_verified_init(self) -> bool:
        """Keep the current init readable without extending a stale epoch."""
        with self.lock:
            if not self._init_published:
                return True
            if (self._verified_failed or not self._verified_authority
                    or not self._verified_token):
                return False
            try:
                index = int(self.redis_client.get(self._init_index_key) or 0)
                if index <= 0:
                    return False
                grant_key, _, generation_key = self._verified_authority._keys(
                    self._verified_scope
                )
                if not self._verified_owner_key:
                    return False
                chunk_key = self._init_chunk_prefix + str(index)
                return self.redis_client.eval(
                    "local epoch = redis.call('HGET', KEYS[1], 'epoch'); "
                    "if not epoch or redis.call('HGET', KEYS[1], 'token') ~= ARGV[1] "
                    "or redis.call('GET', KEYS[2]) ~= ARGV[2] "
                    "or redis.call('GET', KEYS[4]) ~= "
                    "redis.call('HGET', KEYS[1], 'worker') "
                    "or redis.call('GET', KEYS[3] .. ':provenance') "
                    "~= epoch .. ':' .. ARGV[2] then return 0 end; "
                    "redis.call('EXPIRE', KEYS[3], tonumber(ARGV[3])); "
                    "redis.call('EXPIRE', KEYS[3] .. ':provenance', tonumber(ARGV[3])); "
                    "return 1",
                    4, grant_key, generation_key, chunk_key,
                    self._verified_owner_key,
                    self._verified_token, self._verified_generation,
                    max(self.chunk_ttl, 3600),
                ) == 1
            except Exception:
                return False

    def read_active_init(self) -> bytes | None:
        """Read the newest init only if its provenance matches this reader."""
        with self.lock:
            authority = self._verified_authority
            epoch = self._verified_epoch
            generation = self._verified_generation
            scope = self._verified_scope
        if not authority or not epoch or not generation or not self.redis_client:
            return None
        try:
            index = int(self.redis_client.get(self._init_index_key) or 0)
            if index <= 0:
                return None
            return authority.read_buffer_chunk_for_active_generation(
                channel_id=scope,
                grant_epoch=epoch,
                generation_id=generation,
                buffer_chunk_prefix=self._init_chunk_prefix,
                chunk_index=index,
            )
        except Exception:
            return None

    def put_fragment(self, data: bytes) -> bool:
        """Store a single complete fMP4 fragment directly to Redis as its own chunk."""
        if not data or not self.redis_client:
            return False
        try:
            now = time.time()
            with self.lock:
                if (self._verified_failed or self._verified_authority is None
                        or not self._verified_token or not self._verified_generation):
                    return False
                chunk_index = self._verified_authority.publish_buffer_chunk(
                    channel_id=self._verified_scope,
                    grant_token=self._verified_token,
                    generation_id=self._verified_generation,
                    buffer_index_key=self.buffer_index_key,
                    buffer_chunk_prefix=self.buffer_prefix,
                    chunk=data,
                    chunk_ttl=self.chunk_ttl,
                    owner_key=self._verified_owner_key,
                )
                pipe = self.redis_client.pipeline(transaction=False)
                pipe.zadd(self.chunk_timestamps_key, {str(chunk_index): now})
                pipe.zremrangebyscore(self.chunk_timestamps_key, '-inf', now - self.chunk_ttl)
                pipe.expire(self.chunk_timestamps_key, self.chunk_ttl)
                pipe.execute()
                self.index = chunk_index
            self.chunk_available.set()
            self.chunk_available.clear()
            return True
        except Exception as e:
            self.invalidate()
            logger.error(f"[fMP4Buffer:{self.channel_id}] Error putting fragment: {e}")
            return False

    def get_indexed_chunks_for_active_generation(self, *, start_index, count):
        """Preserve Redis indexes when old or expired fragments are omitted."""
        if (type(start_index) is not int or start_index < 0
                or type(count) is not int or count < 0):
            raise ValueError("Invalid verified fMP4 cursor.")
        with self.lock:
            authority = self._verified_authority
            epoch = self._verified_epoch
            generation = self._verified_generation
            scope = self._verified_scope
        if not authority or not epoch or not generation or not self.redis_client:
            raise RuntimeError("No verified fMP4 reader binding.")
        head = int(self.redis_client.get(self.buffer_index_key) or 0)
        result = []
        for index in range(start_index + 1, min(start_index + count, head) + 1):
            data = authority.read_buffer_chunk_for_active_generation(
                channel_id=scope, grant_epoch=epoch, generation_id=generation,
                buffer_chunk_prefix=self.buffer_prefix, chunk_index=index,
            )
            if data is not None:
                result.append((index, data))
        return result

    def current_head(self):
        if not self.redis_client:
            raise RuntimeError("fMP4 Redis is unavailable.")
        return int(self.redis_client.get(self.buffer_index_key) or 0)

    def get_chunks(self, start_index=None):
        """Retrieve chunks from start_index up to current head. Returns (chunks, new_index)."""
        try:
            if not self.redis_client:
                return [], self.index

            current_index = self.redis_client.get(self.buffer_index_key)
            if not current_index:
                return [], self.index

            current_index = int(current_index)

            if start_index is None:
                start_index = max(0, current_index - 5)

            if start_index >= current_index:
                return [], current_index

            chunks = []
            pipe = self.redis_client.pipeline(transaction=False)
            indices = range(start_index + 1, current_index + 1)
            for i in indices:
                pipe.get(RedisKeys.output_buffer_chunk(self.channel_id, self.fmt, i))
            results = pipe.execute()

            for data in results:
                if data:
                    chunks.append(data)

            return chunks, current_index

        except Exception as e:
            logger.error(f"[fMP4Buffer:{self.channel_id}] Error getting chunks: {e}")
            return [], self.index

    def find_chunk_index_by_time(self, seconds_behind):
        """Return the fragment index that was received ~seconds_behind seconds ago.

        Returns an int (last-consumed convention: next read starts at index+1)
        or None if no suitable fragment exists.
        """
        if not self.redis_client or not self._find_chunk_by_time_sha:
            return None
        target_time = time.time() - seconds_behind
        try:
            result = self._find_chunk_by_time_sha(
                keys=[self.chunk_timestamps_key],
                args=[target_time],
            )
            if result is None or int(result) == -1:
                oldest = self.redis_client.zrange(self.chunk_timestamps_key, 0, 0)
                if oldest:
                    return max(0, int(oldest[0]) - 1)
                return None
            return max(0, int(result) - 1)
        except Exception as e:
            logger.error(f"[fMP4Buffer:{self.channel_id}] Error in find_chunk_index_by_time: {e}")
            return None

    def stop(self):
        self.stopping = True

    def cleanup_redis(self):
        """Delete all fMP4 buffer keys for this channel from Redis."""
        if not self.redis_client:
            return
        try:
            prefix = self.buffer_prefix
            cursor = 0
            while True:
                cursor, keys = self.redis_client.scan(cursor, match=f"{prefix}*", count=200)
                if keys:
                    self.redis_client.delete(*keys)
                if cursor == 0:
                    break
            self.redis_client.delete(self.buffer_index_key)
            try:
                self.redis_client.delete(self.chunk_timestamps_key)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[fMP4Buffer:{self.channel_id}] Error during Redis cleanup: {e}")
