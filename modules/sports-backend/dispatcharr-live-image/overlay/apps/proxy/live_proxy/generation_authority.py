"""Isolated Redis ownership-epoch authority prototype.

NOT integrated with Dispatcharr or Atlas admission.

Production use requires real-Redis integration tests, a trusted grant
issuer, deployment lifecycle integration, and atomic media publication.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


class GenerationAuthorityError(RuntimeError):
    """An ownership authority operation could not be verified."""


@dataclass(frozen=True)
class OwnershipGrant:
    epoch: int
    token: str
    worker_id: str


_ACQUIRE = """
-- ATLAS_AUTHORITY_ACQUIRE_V1
if redis.call('GET', KEYS[4]) ~= ARGV[2] then
    return nil
end
if redis.call('EXISTS', KEYS[1]) ~= 0 then
    return nil
end
local epoch = redis.call('INCR', KEYS[2])
redis.call('HSET', KEYS[1],
    'epoch', tostring(epoch),
    'token', ARGV[1],
    'worker', ARGV[2])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
redis.call('DEL', KEYS[3])
return epoch
"""


_RENEW = """
-- ATLAS_RENEW_GENERATION_V1
if redis.call('HGET', KEYS[1], 'token') ~= ARGV[1] then
    return 0
end

if redis.call('GET', KEYS[3])
   ~= redis.call('HGET', KEYS[1], 'worker') then
    return 0
end

if redis.call('GET', KEYS[2]) ~= ARGV[2] then
    return 0
end

if redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3])) ~= 1 then
    return 0
end

return 1
"""


_RELEASE = """
-- ATLAS_AUTHORITY_RELEASE_V1
if redis.call('HGET', KEYS[1], 'token') ~= ARGV[1] then
    return 0
end
redis.call('DEL', KEYS[1], KEYS[2])
return 1
"""

_ACTIVATE = """
-- ATLAS_AUTHORITY_ACTIVATE_V1
if redis.call('HGET', KEYS[1], 'token') ~= ARGV[1] then
    return 0
end
redis.call('SET', KEYS[2], ARGV[2])
return 1
"""


_PUBLISH_CHUNK = """
-- ATLAS_ATOMIC_PUBLISH_V1
local epoch = redis.call('HGET', KEYS[1], 'epoch')
if not epoch
   or redis.call('HGET', KEYS[1], 'token') ~= ARGV[1]
   or redis.call('GET', KEYS[2]) ~= ARGV[2]
   or redis.call('GET', KEYS[4])
       ~= redis.call('HGET', KEYS[1], 'worker') then
    return 0
end

local index = redis.call('INCR', KEYS[3])
local chunk_key = ARGV[3] .. tostring(index)

redis.call('SETEX', chunk_key, tonumber(ARGV[4]), ARGV[5])
redis.call(
    'SETEX',
    chunk_key .. ':provenance',
    tonumber(ARGV[4]),
    epoch .. ':' .. ARGV[2]
)

return index
"""

_READ_CHUNK = """
-- ATLAS_ATOMIC_READ_V1
local epoch = redis.call('HGET', KEYS[1], 'epoch')
if not epoch
   or redis.call('HGET', KEYS[1], 'token') ~= ARGV[1]
   or redis.call('GET', KEYS[2]) ~= ARGV[2] then
    return nil
end

local chunk_key = ARGV[3] .. ARGV[4]

if redis.call('GET', chunk_key .. ':provenance')
   ~= epoch .. ':' .. ARGV[2] then
    return nil
end

return redis.call('GET', chunk_key)
"""



_CURRENT_GENERATION = """
-- ATLAS_CURRENT_GENERATION_V1
local epoch = redis.call('HGET', KEYS[1], 'epoch')
if not epoch then
    return nil
end

local generation = redis.call('GET', KEYS[2])
if not generation then
    return nil
end

return {epoch, generation}
"""

_READ_ACTIVE_CHUNK = """
-- ATLAS_ACTIVE_READ_V1
local epoch = redis.call('HGET', KEYS[1], 'epoch')

if not epoch
   or epoch ~= ARGV[1]
   or redis.call('GET', KEYS[2]) ~= ARGV[2] then
    return nil
end

local chunk_key = ARGV[3] .. ARGV[4]

if redis.call('GET', chunk_key .. ':provenance')
   ~= epoch .. ':' .. ARGV[2] then
    return nil
end

return redis.call('GET', chunk_key)
"""


_CURRENT = """
-- ATLAS_AUTHORITY_CURRENT_V1
if redis.call('EXISTS', KEYS[1]) == 0 then
    return nil
end
return {
    redis.call('HGET', KEYS[1], 'epoch'),
    redis.call('HGET', KEYS[1], 'token'),
    redis.call('HGET', KEYS[1], 'worker')
}
"""


def _valid(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise GenerationAuthorityError(f"Invalid {name}.")
    return value


def _decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


class GenerationAuthority:
    """Prototype using Redis as the authoritative grant store."""

    def __init__(self, redis_client, *, lease_seconds: int = 30):
        if not isinstance(lease_seconds, int) or lease_seconds <= 0:
            raise ValueError("lease_seconds must be a positive integer")
        self.redis = redis_client
        self.lease_seconds = lease_seconds

    @staticmethod
    def _keys(channel_id: str) -> tuple[str, str, str]:
        channel = _valid(channel_id, "channel ID")
        prefix = f"atlas:dispatcharr:attestation:{channel}"
        return (
            f"{prefix}:grant",
            f"{prefix}:epoch",
            f"{prefix}:generation",
        )

    def _eval(self, script: str, keys: tuple[str, ...], *args):
        if self.redis is None:
            raise GenerationAuthorityError(
                "Redis authority is unavailable."
            )
        try:
            return self.redis.eval(
                script,
                len(keys),
                *keys,
                *args,
            )
        except Exception as exc:
            raise GenerationAuthorityError(
                "Redis authority operation failed."
            ) from exc

    def acquire(
        self,
        *,
        channel_id: str,
        worker_id: str,
        owner_key: str,
    ) -> OwnershipGrant:
        worker = _valid(worker_id, "worker ID")
        keys = self._keys(channel_id) + (
            _valid(owner_key, "legacy owner key"),
        )
        token = uuid4().hex

        result = self._eval(
            _ACQUIRE,
            keys,
            token,
            worker,
            self.lease_seconds,
        )

        if result is None or int(result) <= 0:
            raise GenerationAuthorityError(
                "An ownership grant is already held."
            )

        return OwnershipGrant(
            epoch=int(result),
            token=token,
            worker_id=worker,
        )

    def current_grant(
        self,
        channel_id: str,
    ) -> OwnershipGrant | None:
        keys = self._keys(channel_id)
        result = self._eval(_CURRENT, keys[:1])

        if result is None:
            return None

        if not isinstance(result, (list, tuple)) or len(result) != 3:
            raise GenerationAuthorityError(
                "Unexpected authority response."
            )

        try:
            grant = OwnershipGrant(
                epoch=int(result[0]),
                token=_decode(result[1]),
                worker_id=_decode(result[2]),
            )
        except (TypeError, ValueError, UnicodeError) as exc:
            raise GenerationAuthorityError(
                "Invalid authority response."
            ) from exc

        if (
            grant.epoch <= 0
            or not grant.token
            or not grant.worker_id
        ):
            raise GenerationAuthorityError(
                "Incomplete authority response."
            )

        return grant

    def activate_generation(
        self,
        *,
        channel_id: str,
        grant_token: str,
        generation_id: str,
    ) -> None:
        token = _valid(grant_token, "grant token")
        generation = _valid(generation_id, "generation ID")
        keys = self._keys(channel_id)

        if self._eval(
            _ACTIVATE,
            (keys[0], keys[2]),
            token,
            generation,
        ) != 1:
            raise GenerationAuthorityError(
                "The ownership grant is no longer current."
            )

    def renew(
        self,
        *,
        channel_id: str,
        grant_token: str,
        generation_id: str,
        owner_key: str,
    ) -> bool:
        """Renew only the currently matching grant and generation.

        Renewal can extend an existing verified epoch. It can never
        create a new grant, replace a token, or reactivate an expired
        generation.
        """
        token = _valid(
            grant_token,
            "grant token",
        )
        generation = _valid(
            generation_id,
            "generation ID",
        )

        grant_key, _, generation_key = self._keys(
            channel_id
        )

        renewal_keys = (
            grant_key, generation_key,
            _valid(owner_key, "legacy owner key"),
        )

        result = self._eval(
            _RENEW,
            renewal_keys,
            token,
            generation,
            self.lease_seconds,
        )

        try:
            renewed = int(result)
        except (TypeError, ValueError) as exc:
            raise GenerationAuthorityError(
                "Invalid Redis renewal response."
            ) from exc

        return renewed == 1

    def release(
        self,
        *,
        channel_id: str,
        grant_token: str,
    ) -> None:
        token = _valid(grant_token, "grant token")
        keys = self._keys(channel_id)

        if self._eval(
            _RELEASE,
            (keys[0], keys[2]),
            token,
        ) != 1:
            raise GenerationAuthorityError(
                "The ownership grant is no longer current."
            )

    def publish_chunk(
        self,
        *,
        channel_id: str,
        grant_token: str,
        generation_id: str,
        chunk: bytes,
        chunk_ttl: int = 60,
    ) -> int:
        """Atomically fence and publish one already-framed media chunk.

        This prototype is not wired to Dispatcharr's packet accumulator.
        The caller must not be allowed to invent grant or generation
        credentials from untrusted viewer requests.
        """
        token = _valid(grant_token, "grant token")
        generation = _valid(generation_id, "generation ID")

        if not isinstance(chunk, bytes) or not chunk:
            raise GenerationAuthorityError("Invalid media chunk.")
        if (
            not isinstance(chunk_ttl, int)
            or chunk_ttl <= 0
        ):
            raise GenerationAuthorityError("Invalid chunk TTL.")

        grant_key, _, generation_key = self._keys(channel_id)
        prefix = f"atlas:dispatcharr:attestation:{channel_id}:"
        index_key = prefix + "chunk-index"
        chunk_prefix = prefix + "chunk:"

        result = self._eval(
            _PUBLISH_CHUNK,
            (grant_key, generation_key, index_key),
            token,
            generation,
            chunk_prefix,
            chunk_ttl,
            chunk,
        )

        try:
            index = int(result)
        except (TypeError, ValueError) as exc:
            raise GenerationAuthorityError(
                "Invalid Redis publication response."
            ) from exc

        if index <= 0:
            raise GenerationAuthorityError(
                "The publication grant or generation is stale."
            )

        return index

    def read_chunk_for_generation(
        self,
        *,
        channel_id: str,
        grant_token: str,
        generation_id: str,
        chunk_index: int,
    ) -> bytes | None:
        """Return bytes only when their stored provenance is current.

        A successful retrieval is not proof that an HTTP client
        subsequently received the bytes.
        """
        token = _valid(grant_token, "grant token")
        generation = _valid(generation_id, "generation ID")

        if not isinstance(chunk_index, int) or chunk_index <= 0:
            raise GenerationAuthorityError("Invalid chunk index.")

        grant_key, _, generation_key = self._keys(channel_id)
        prefix = f"atlas:dispatcharr:attestation:{channel_id}:chunk:"

        result = self._eval(
            _READ_CHUNK,
            (grant_key, generation_key),
            token,
            generation,
            prefix,
            chunk_index,
        )

        if result is None:
            return None

        if isinstance(result, bytes):
            return result

        # redis-cli --json decodes text. This branch is ONLY for the
        # synthetic ASCII integration payloads; real media requires
        # a binary-safe Redis client.
        if isinstance(result, str) and result.isascii():
            return result.encode("ascii")

        raise GenerationAuthorityError(
            "Redis returned a non-binary-safe chunk representation."
        )

    def publish_buffer_chunk(
        self,
        *,
        channel_id: str,
        grant_token: str,
        generation_id: str,
        buffer_index_key: str,
        buffer_chunk_prefix: str,
        chunk: bytes,
        chunk_ttl: int,
        owner_key: str,
    ) -> int:
        """Publish into the existing Dispatcharr buffer namespace.

        This is a staged integration interface, not live worker
        attestation. Only trusted buffer code may supply these keys.
        """
        token = _valid(grant_token, "grant token")
        generation = _valid(generation_id, "generation ID")
        index_key = _valid(buffer_index_key, "buffer index key")
        chunk_prefix = _valid(
            buffer_chunk_prefix, "buffer chunk prefix"
        )

        if not isinstance(chunk, bytes) or not chunk:
            raise GenerationAuthorityError("Invalid media chunk.")

        if (
            isinstance(chunk_ttl, bool)
            or not isinstance(chunk_ttl, int)
            or chunk_ttl <= 0
        ):
            raise GenerationAuthorityError("Invalid chunk TTL.")

        grant_key, _, generation_key = self._keys(channel_id)
        keys = (
            grant_key, generation_key, index_key,
            _valid(owner_key, "legacy owner key"),
        )

        result = self._eval(
            _PUBLISH_CHUNK,
            keys,
            token,
            generation,
            chunk_prefix,
            chunk_ttl,
            chunk,
        )

        try:
            index = int(result)
        except (TypeError, ValueError) as exc:
            raise GenerationAuthorityError(
                "Invalid Redis publication response."
            ) from exc

        if index <= 0:
            raise GenerationAuthorityError(
                "The publication grant or generation is stale."
            )

        return index

    def read_buffer_chunk_for_generation(
        self,
        *,
        channel_id: str,
        grant_token: str,
        generation_id: str,
        buffer_chunk_prefix: str,
        chunk_index: int,
    ) -> bytes | None:
        """Read one original buffer index with its provenance checked.

        Never infer a chunk's index from its position in a filtered
        list. This method does not prove downstream viewer delivery.
        """
        token = _valid(grant_token, "grant token")
        generation = _valid(generation_id, "generation ID")
        chunk_prefix = _valid(
            buffer_chunk_prefix, "buffer chunk prefix"
        )

        if (
            isinstance(chunk_index, bool)
            or not isinstance(chunk_index, int)
            or chunk_index <= 0
        ):
            raise GenerationAuthorityError("Invalid chunk index.")

        grant_key, _, generation_key = self._keys(channel_id)

        result = self._eval(
            _READ_CHUNK,
            (grant_key, generation_key),
            token,
            generation,
            chunk_prefix,
            chunk_index,
        )

        if result is None:
            return None

        if isinstance(result, bytes):
            return result

        if isinstance(result, str) and result.isascii():
            # Test-only ASCII CLI adapter compatibility.
            return result.encode("ascii")

        raise GenerationAuthorityError(
            "Redis returned a non-binary-safe chunk representation."
        )

    def current_generation(self, channel_id: str):
        """Return the active reader attestation without the writer token.

        Result is ``(epoch, generation_id)`` or ``None``.
        This is intentionally insufficient to publish media.
        """
        grant_key, _, generation_key = self._keys(channel_id)

        result = self._eval(
            _CURRENT_GENERATION,
            (grant_key, generation_key),
        )

        if result is None:
            return None

        if not isinstance(result, (list, tuple)) or len(result) != 2:
            raise GenerationAuthorityError(
                "Invalid Redis generation response."
            )

        raw_epoch, raw_generation = result

        if isinstance(raw_epoch, bytes):
            raw_epoch = raw_epoch.decode("ascii")

        if isinstance(raw_generation, bytes):
            raw_generation = raw_generation.decode("utf-8")

        try:
            epoch = int(raw_epoch)
        except (TypeError, ValueError) as exc:
            raise GenerationAuthorityError(
                "Invalid Redis generation epoch."
            ) from exc

        generation = _valid(
            raw_generation,
            "generation ID",
        )

        if epoch <= 0:
            raise GenerationAuthorityError(
                "Invalid Redis generation epoch."
            )

        return epoch, generation

    def read_buffer_chunk_for_active_generation(
        self,
        *,
        channel_id: str,
        grant_epoch: int,
        generation_id: str,
        buffer_chunk_prefix: str,
        chunk_index: int,
    ) -> bytes | None:
        """Read verified media without exposing publication authority.

        The active Redis grant epoch and generation are checked in
        the same Lua operation as the chunk provenance.
        """
        if (
            isinstance(grant_epoch, bool)
            or not isinstance(grant_epoch, int)
            or grant_epoch <= 0
        ):
            raise GenerationAuthorityError(
                "Invalid grant epoch."
            )

        generation = _valid(
            generation_id,
            "generation ID",
        )
        chunk_prefix = _valid(
            buffer_chunk_prefix,
            "buffer chunk prefix",
        )

        if (
            isinstance(chunk_index, bool)
            or not isinstance(chunk_index, int)
            or chunk_index <= 0
        ):
            raise GenerationAuthorityError(
                "Invalid chunk index."
            )

        grant_key, _, generation_key = self._keys(channel_id)

        result = self._eval(
            _READ_ACTIVE_CHUNK,
            (grant_key, generation_key),
            grant_epoch,
            generation,
            chunk_prefix,
            chunk_index,
        )

        if result is None:
            return None

        if isinstance(result, bytes):
            return result

        if isinstance(result, str) and result.isascii():
            # Test-adapter compatibility only. Production Redis
            # clients return binary media as bytes.
            return result.encode("ascii")

        raise GenerationAuthorityError(
            "Redis returned a non-binary-safe chunk representation."
        )

    def expire_for_test(
        self,
        *,
        channel_id: str,
        grant_token: str,
    ) -> None:
        """TEST ONLY: model expiration in the isolated fake backend.

        Never use this method to revoke a real Redis grant.
        """
        token = _valid(grant_token, "grant token")
        keys = self._keys(channel_id)

        if not getattr(self.redis, "_atlas_test_backend", False):
            raise GenerationAuthorityError(
                "Synthetic expiration is restricted to test backends."
            )

        try:
            self.redis.expire_grant_for_test(keys, token)
        except Exception as exc:
            raise GenerationAuthorityError(
                "Synthetic expiration failed."
            ) from exc
