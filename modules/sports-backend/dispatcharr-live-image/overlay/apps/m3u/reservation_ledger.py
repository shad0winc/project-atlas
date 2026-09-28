"""Isolated v1 reservation ledger. Do not enable before all callers migrate.

Redis keys contain only opaque identities and hashed credential scopes. Records
persist until an owner-verified release or explicit orphan reconciliation.
The cutover key must be set only after legacy sessions have drained.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Callable, Literal
from uuid import UUID


CUTOVER_KEY = "atlas:reservation:v1:cutover"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class ReservationError(RuntimeError):
    """Reservation is unavailable or Redis state needs reconciliation."""


class ReservationBusy(ReservationError):
    """The owner already has a reservation; it must be attested before reuse."""


class ReservationFull(ReservationError):
    """A verified profile, account, or credential capacity is exhausted."""


@dataclass(frozen=True, slots=True)
class ReservationSpec:
    mode: Literal["live", "vod", "timeshift"]
    owner_id: str
    stream_id: int
    profile_id: int
    account_id: int
    credential_scope: str
    profile_capacity: int
    account_capacity: int
    credential_capacity: int

    def __post_init__(self) -> None:
        if self.mode not in {"live", "vod", "timeshift"}:
            raise ValueError("Invalid reservation mode")
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("Missing owner identity")
        if any(type(value) is not int or value < 1 for value in (
            self.stream_id, self.profile_id, self.account_id,
            self.profile_capacity, self.account_capacity,
            self.credential_capacity,
        )):
            raise ValueError("A bounded positive identity and capacity is required")
        if not isinstance(self.credential_scope, str) or not _HEX64.fullmatch(
            self.credential_scope
        ):
            raise ValueError("An opaque verified credential scope is required")

    @property
    def owner_key(self) -> str:
        digest = hashlib.sha256(self.owner_id.encode("utf-8")).hexdigest()
        return f"atlas:reservation:v1:owner:{self.mode}:{digest}"

    @property
    def profile_key(self) -> str:
        return f"profile_connections:{self.profile_id}"

    @property
    def account_key(self) -> str:
        return f"atlas:reservation:v1:account:{self.account_id}"

    @property
    def credential_key(self) -> str:
        return f"atlas:reservation:v1:credential:{self.credential_scope}"


_RESERVE = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('EXISTS', KEYS[2]) ~= 0 or redis.call('EXISTS', KEYS[3]) ~= 0
then return {0, 0} end
for i = 4, 6 do
  local raw = redis.call('GET', KEYS[i]) or '0'
  local count = tonumber(raw)
  local limit = tonumber(ARGV[i - 2])
  if not count or count < 0 or count ~= math.floor(count)
     or not limit or limit < 1 then return {-2, 0} end
  if count >= limit then return {-1, count} end
end
redis.call('INCR', KEYS[4])
redis.call('INCR', KEYS[5])
redis.call('INCR', KEYS[6])
redis.call('HSET', KEYS[3], 'token', ARGV[1], 'owner', KEYS[2],
           'stream', ARGV[5], 'profile', KEYS[4], 'account', KEYS[5],
           'credential', KEYS[6], 'mode', ARGV[6], 'state', 'pending',
           'profile_id', ARGV[7], 'account_id', ARGV[8])
redis.call('SET', KEYS[2], ARGV[1])
return {1, tonumber(redis.call('GET', KEYS[4]))}
"""


_RESERVE_LIVE_CHANNEL = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('GET', KEYS[8]) ~= ARGV[9] then return {0, 0} end
if redis.call('EXISTS', KEYS[2]) ~= 0
   or redis.call('EXISTS', KEYS[3]) ~= 0
   or redis.call('EXISTS', KEYS[7]) ~= 0 then return {0, 0} end
for i = 4, 6 do
  local raw = redis.call('GET', KEYS[i]) or '0'
  local count = tonumber(raw)
  local limit = tonumber(ARGV[i - 2])
  if not count or count < 0 or count ~= math.floor(count)
     or not limit or limit < 1 then return {-2, 0} end
  if count >= limit then return {-1, count} end
end
for i = 4, 6 do redis.call('INCR', KEYS[i]) end
redis.call('HSET', KEYS[3], 'token', ARGV[1], 'owner', KEYS[2],
           'stream', ARGV[5], 'profile', KEYS[4], 'account', KEYS[5],
           'credential', KEYS[6], 'mode', 'live', 'state', 'pending',
           'profile_id', ARGV[7], 'account_id', ARGV[8],
           'channel_alias', KEYS[7])
redis.call('SET', KEYS[2], ARGV[1])
redis.call('HSET', KEYS[7], 'token', ARGV[1],
           'owner_lease', ARGV[9], 'stream_id', ARGV[5],
           'profile_id', ARGV[7], 'account_id', ARGV[8])
return {1, tonumber(redis.call('GET', KEYS[4]))}
"""


_RELEASE_PENDING_LIVE_CHANNEL = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('GET', KEYS[8]) ~= ARGV[2]
   or redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'live'
   or redis.call('HGET', KEYS[3], 'state') ~= 'pending'
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[4]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[6]
   or redis.call('HGET', KEYS[7], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[7], 'owner_lease') ~= ARGV[2]
   or redis.call('HGET', KEYS[7], 'stream_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[7], 'profile_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[7], 'account_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[3]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'channel_alias') ~= KEYS[7]
then return {0, 0} end
for i = 4, 6 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count)
  then return {-2, 0} end
end
for i = 4, 6 do redis.call('DECR', KEYS[i]) end
redis.call('DEL', KEYS[7], KEYS[3], KEYS[2])
return {1, 0}
"""

_RELEASE = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1] then return {0, 0} end
if redis.call('HEXISTS', KEYS[3], 'channel_alias') ~= 0
then return {-2, 0} end
if redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[4]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[6]
then return {-2, 0} end
if redis.call('HGET', KEYS[3], 'state') == 'active'
   and redis.call('HGET', KEYS[3], 'mode') ~= 'live'
then return {-2, 0} end
for i = 4, 6 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count)
  then return {-2, 0} end
end
redis.call('DECR', KEYS[4])
redis.call('DECR', KEYS[5])
redis.call('DECR', KEYS[6])
redis.call('DEL', KEYS[3], KEYS[2])
return {1, 0}
"""

_SWITCH = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1] then return {0, 0} end
if redis.call('HEXISTS', KEYS[3], 'channel_alias') ~= 0
then return {-2, 0} end
if redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[4]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[6]
then return {-2, 0} end
if redis.call('HGET', KEYS[3], 'state') == 'active'
   and redis.call('HGET', KEYS[3], 'mode') ~= 'live'
then return {-2, 0} end
for i = 4, 6 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count)
  then return {-2, 0} end
end
for i = 7, 9 do
  if KEYS[i] ~= KEYS[i - 3] then
    local count = tonumber(redis.call('GET', KEYS[i]) or '0')
    local limit = tonumber(ARGV[i - 5])
    if not count or count < 0 or count ~= math.floor(count)
       or not limit or limit < 1 then return {-2, 0} end
    if count >= limit then return {-1, count} end
  end
end
for i = 7, 9 do
  if KEYS[i] ~= KEYS[i - 3] then
    redis.call('INCR', KEYS[i])
    redis.call('DECR', KEYS[i - 3])
  end
end
local old_epoch = redis.call('HGET', KEYS[3], 'grant_epoch')
local old_generation = redis.call('HGET', KEYS[3], 'generation')
if old_epoch and old_generation then
  redis.call('HSET', KEYS[3], 'fenced_epoch', old_epoch,
             'fenced_generation', old_generation)
end
redis.call('HSET', KEYS[3], 'stream', ARGV[5], 'profile', KEYS[7],
           'account', KEYS[8], 'credential', KEYS[9], 'state', 'pending',
           'profile_id', ARGV[6], 'account_id', ARGV[7])
redis.call('HDEL', KEYS[3], 'grant_epoch', 'generation', 'worker',
           'grant_token')
return {1, tonumber(redis.call('GET', KEYS[7]))}
"""


_ACTIVATE_LIVE = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1] then return 0 end
if redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'live'
   or redis.call('HGET', KEYS[3], 'state') ~= 'pending'
then return -2 end
local alias = redis.call('HGET', KEYS[3], 'channel_alias')
if alias then
  if alias ~= KEYS[9]
     or redis.call('HGET', KEYS[9], 'token') ~= ARGV[1]
     or redis.call('HEXISTS', KEYS[9], 'stopped_epoch') ~= 0
     or redis.call('HGET', KEYS[9], 'owner_lease') ~= ARGV[5]
     or redis.call('HGET', KEYS[9], 'stream_id') ~=
        redis.call('HGET', KEYS[3], 'stream')
     or redis.call('HGET', KEYS[9], 'profile_id') ~=
        redis.call('HGET', KEYS[3], 'profile_id')
     or redis.call('HGET', KEYS[9], 'account_id') ~=
        redis.call('HGET', KEYS[3], 'account_id')
  then return 0 end
end
if redis.call('HGET', KEYS[3], 'fenced_epoch') == ARGV[3]
   and redis.call('HGET', KEYS[3], 'fenced_generation') == ARGV[4]
then return 0 end
if redis.call('HGET', KEYS[4], 'token') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'epoch') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'worker') ~= ARGV[5]
   or redis.call('GET', KEYS[5]) ~= ARGV[4]
   or redis.call('GET', KEYS[6]) ~= ARGV[5]
   or redis.call('GET', KEYS[8]) ~= ARGV[3] .. ':' .. ARGV[4]
   or redis.call('EXISTS', KEYS[7]) ~= 1
then return 0 end
for _, field in ipairs({'profile', 'account', 'credential'}) do
  local key = redis.call('HGET', KEYS[3], field)
  if not key then return -2 end
  local count = tonumber(redis.call('GET', key) or '')
  if not count or count < 1 or count ~= math.floor(count) then return -2 end
end
redis.call('HSET', KEYS[3], 'state', 'active', 'grant_epoch', ARGV[3],
           'generation', ARGV[4], 'worker', ARGV[5],
           'grant_token', ARGV[2])
return 1
"""


_ATTEST_LIVE_JOIN = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3} end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1] then return {0} end
if redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'live'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[10]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[11]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[12]
then return {-2} end
local epoch = redis.call('HGET', KEYS[3], 'grant_epoch')
local generation = redis.call('HGET', KEYS[3], 'generation')
local worker = redis.call('HGET', KEYS[3], 'worker')
local alias = redis.call('HGET', KEYS[3], 'channel_alias')
if alias then
  if alias ~= KEYS[9]
     or redis.call('HGET', KEYS[9], 'token') ~= ARGV[1]
     or redis.call('HEXISTS', KEYS[9], 'stopped_epoch') ~= 0
     or redis.call('HGET', KEYS[9], 'owner_lease') ~= worker
     or redis.call('HGET', KEYS[9], 'stream_id') ~=
        redis.call('HGET', KEYS[3], 'stream')
     or redis.call('HGET', KEYS[9], 'profile_id') ~=
        redis.call('HGET', KEYS[3], 'profile_id')
     or redis.call('HGET', KEYS[9], 'account_id') ~=
        redis.call('HGET', KEYS[3], 'account_id')
  then return {0} end
end
if epoch ~= ARGV[2] or generation ~= ARGV[3]
   or redis.call('HGET', KEYS[3], 'grant_token') ~=
      redis.call('HGET', KEYS[4], 'token')
   or redis.call('HGET', KEYS[4], 'epoch') ~= epoch
   or redis.call('HGET', KEYS[4], 'worker') ~= worker
   or redis.call('GET', KEYS[5]) ~= generation
   or redis.call('GET', KEYS[6]) ~= worker
   or redis.call('GET', KEYS[8]) ~= epoch .. ':' .. generation
   or redis.call('EXISTS', KEYS[7]) ~= 1
then return {0} end
local ids = {}
for _, field in ipairs({'stream', 'profile_id', 'account_id'}) do
  local value = redis.call('HGET', KEYS[3], field)
  if not value or not tonumber(value) or tonumber(value) < 1
  then return {-2} end
  table.insert(ids, value)
end
for i = 10, 12 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  local limit = tonumber(ARGV[i - 6])
  if not count or count < 1 or count ~= math.floor(count)
     or not limit or limit < 1 or count > limit then return {-2} end
end
return {1, ids[1], ids[2], ids[3]}
"""


_ACK_LIVE_STOP = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('GET', KEYS[8]) ~= ARGV[2]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'live'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'channel_alias') ~= KEYS[7]
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[3]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[4]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[6]
   or redis.call('HGET', KEYS[3], 'worker') ~= ARGV[2]
   or redis.call('HGET', KEYS[3], 'grant_token') ~= ARGV[6]
   or redis.call('HGET', KEYS[3], 'grant_epoch') ~= ARGV[7]
   or redis.call('HGET', KEYS[3], 'generation') ~= ARGV[8]
   or redis.call('HGET', KEYS[7], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[7], 'owner_lease') ~= ARGV[2]
   or redis.call('HGET', KEYS[7], 'stream_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[7], 'profile_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[7], 'account_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[9], 'token') ~= ARGV[6]
   or redis.call('HGET', KEYS[9], 'epoch') ~= ARGV[7]
   or redis.call('HGET', KEYS[9], 'worker') ~= ARGV[2]
   or redis.call('GET', KEYS[10]) ~= ARGV[8]
then return 0 end
for i = 4, 6 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count) then return -2 end
end
redis.call('HSET', KEYS[7], 'stopped_epoch', ARGV[7],
           'stopped_generation', ARGV[8])
return 1
"""


_RELEASE_ACTIVE_LIVE = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('GET', KEYS[8]) ~= ARGV[2]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'live'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'channel_alias') ~= KEYS[7]
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[3]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[4]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[6]
   or redis.call('HGET', KEYS[3], 'worker') ~= ARGV[2]
   or redis.call('HGET', KEYS[3], 'grant_token') ~= ARGV[6]
   or redis.call('HGET', KEYS[3], 'grant_epoch') ~= ARGV[7]
   or redis.call('HGET', KEYS[3], 'generation') ~= ARGV[8]
   or redis.call('HGET', KEYS[7], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[7], 'owner_lease') ~= ARGV[2]
   or redis.call('HGET', KEYS[7], 'stream_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[7], 'profile_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[7], 'account_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[7], 'stopped_epoch') ~= ARGV[7]
   or redis.call('HGET', KEYS[7], 'stopped_generation') ~= ARGV[8]
   or redis.call('HGET', KEYS[9], 'token') ~= ARGV[6]
   or redis.call('HGET', KEYS[9], 'epoch') ~= ARGV[7]
   or redis.call('HGET', KEYS[9], 'worker') ~= ARGV[2]
   or redis.call('GET', KEYS[10]) ~= ARGV[8]
then return 0 end
for i = 4, 6 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count) then return -2 end
end
for i = 4, 6 do redis.call('DECR', KEYS[i]) end
redis.call('DEL', KEYS[7], KEYS[3], KEYS[2])
return 1
"""


_SWITCH_LIVE_CHANNEL = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('GET', KEYS[11]) ~= ARGV[2]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'live'
   or redis.call('HGET', KEYS[3], 'channel_alias') ~= KEYS[10]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[4]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[6]
   or redis.call('HGET', KEYS[10], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[10], 'owner_lease') ~= ARGV[2]
   or redis.call('HGET', KEYS[10], 'stream_id') ~=
      redis.call('HGET', KEYS[3], 'stream')
   or redis.call('HGET', KEYS[10], 'profile_id') ~=
      redis.call('HGET', KEYS[3], 'profile_id')
   or redis.call('HGET', KEYS[10], 'account_id') ~=
      redis.call('HGET', KEYS[3], 'account_id')
then return {0, 0} end
local state = redis.call('HGET', KEYS[3], 'state')
if state == 'active' then
  if redis.call('HGET', KEYS[3], 'worker') ~= ARGV[2]
     or redis.call('HGET', KEYS[3], 'grant_token') ~= ARGV[9]
     or redis.call('HGET', KEYS[3], 'grant_epoch') ~= ARGV[10]
     or redis.call('HGET', KEYS[3], 'generation') ~= ARGV[11]
     or redis.call('HGET', KEYS[10], 'stopped_epoch') ~= ARGV[10]
     or redis.call('HGET', KEYS[10], 'stopped_generation') ~= ARGV[11]
     or redis.call('HGET', KEYS[12], 'token') ~= ARGV[9]
     or redis.call('HGET', KEYS[12], 'epoch') ~= ARGV[10]
     or redis.call('HGET', KEYS[12], 'worker') ~= ARGV[2]
     or redis.call('GET', KEYS[13]) ~= ARGV[11]
  then return {0, 0} end
elseif state == 'pending' then
  if redis.call('HEXISTS', KEYS[10], 'stopped_epoch') ~= 0
     or ARGV[9] ~= '' or ARGV[10] ~= '' or ARGV[11] ~= ''
  then return {0, 0} end
else return {-2, 0} end
for i = 4, 6 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count)
  then return {-2, 0} end
end
for i = 7, 9 do
  if KEYS[i] ~= KEYS[i - 3] then
    local count = tonumber(redis.call('GET', KEYS[i]) or '0')
    local limit = tonumber(ARGV[i - 4])
    if not count or count < 0 or count ~= math.floor(count)
       or not limit or limit < 1 then return {-2, 0} end
    if count >= limit then return {-1, count} end
  end
end
for i = 7, 9 do
  if KEYS[i] ~= KEYS[i - 3] then
    redis.call('INCR', KEYS[i])
    redis.call('DECR', KEYS[i - 3])
  end
end
if state == 'active' then
  redis.call('HSET', KEYS[3], 'fenced_epoch', ARGV[10],
             'fenced_generation', ARGV[11])
end
redis.call('HSET', KEYS[3], 'stream', ARGV[6], 'profile', KEYS[7],
           'account', KEYS[8], 'credential', KEYS[9],
           'profile_id', ARGV[7], 'account_id', ARGV[8], 'state', 'pending')
redis.call('HDEL', KEYS[3], 'grant_token', 'grant_epoch', 'generation', 'worker')
redis.call('HSET', KEYS[10], 'stream_id', ARGV[6],
           'profile_id', ARGV[7], 'account_id', ARGV[8])
redis.call('HDEL', KEYS[10], 'stopped_epoch', 'stopped_generation')
return {1, tonumber(redis.call('GET', KEYS[7]))}
"""


def _record_key(token: str) -> str:
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("Invalid reservation token")
    return f"atlas:reservation:v1:record:{token}"


def _live_keys(spec: ReservationSpec, token: str, *, channel_id: str,
               worker_id: str, chunk_index: int) -> tuple[str, ...]:
    if spec.mode != "live":
        raise ValueError("Only live reservations can attest an upstream")
    if (not isinstance(channel_id, str)
        or str(UUID(channel_id)) != channel_id
        or not isinstance(worker_id, str)
        or not worker_id.strip()
        or spec.owner_id != f"{channel_id}|{worker_id}"):
        raise ValueError("The live channel and owner lifecycle must match")
    if type(chunk_index) is not int or chunk_index < 1:
        raise ValueError("A published raw TS chunk index is required")
    prefix = f"atlas:dispatcharr:attestation:{channel_id}"
    chunk = f"live:channel:{channel_id}:input:buffer:chunk:{chunk_index}"
    return (CUTOVER_KEY, spec.owner_key, _record_key(token),
            prefix + ":grant", prefix + ":generation",
            f"live:channel:{channel_id}:owner", chunk,
            chunk + ":provenance",
            f"atlas:reservation:v1:live:channel:{channel_id}")


def _vod_keys(spec: ReservationSpec, token: str, *, session_id: str,
              generation_id: str) -> tuple[str, ...]:
    """Locate one VOD session lifecycle without exposing its upstream URL."""
    if spec.mode != "vod":
        raise ValueError("Only VOD reservations can bind a VOD session")
    if (not isinstance(session_id, str) or not session_id
        or "|" in session_id or session_id != session_id.strip()
        or not isinstance(generation_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", generation_id)
        or spec.owner_id != f"{session_id}|{generation_id}"):
        raise ValueError("The VOD session and generation must match its owner")
    return (CUTOVER_KEY, spec.owner_key, _record_key(token),
            f"vod_persistent_connection:{session_id}")


def _vod_viewer_identity(user_id: int, content_uuid: str) -> None:
    if type(user_id) is not int or user_id < 1:
        raise ValueError("An authenticated VOD user is required")
    if (not isinstance(content_uuid, str)
        or str(UUID(content_uuid)) != content_uuid):
        raise ValueError("A canonical VOD content UUID is required")


_BIND_VOD = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1] then return 0 end
if redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'vod'
   or redis.call('HGET', KEYS[3], 'state') ~= 'pending'
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[4]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[5]
then return -2 end
if redis.call('EXISTS', KEYS[4]) ~= 1
   or redis.call('HGET', KEYS[4], 'm3u_profile_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[4], 'content_uuid') ~= ARGV[7]
   or redis.call('HGET', KEYS[4], 'active_streams') ~= '0'
   or redis.call('HEXISTS', KEYS[4], 'atlas_reservation_token') ~= 0
   or redis.call('HEXISTS', KEYS[4], 'atlas_reservation_generation') ~= 0
then return 0 end
for _, field in ipairs({'profile', 'account', 'credential'}) do
  local key = redis.call('HGET', KEYS[3], field)
  if not key then return -2 end
  local count = tonumber(redis.call('GET', key) or '')
  if not count or count < 1 or count ~= math.floor(count) then return -2 end
end
redis.call('HSET', KEYS[4], 'atlas_reservation_token', ARGV[1],
           'atlas_reservation_generation', ARGV[2])
redis.call('HSET', KEYS[3], 'state', 'active')
return 1
"""


_VOD_JOIN = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'vod'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'm3u_profile_id') ~=
      redis.call('HGET', KEYS[3], 'profile_id')
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'content_uuid') ~= ARGV[4]
then return {0, 0} end
local active = tonumber(redis.call('HGET', KEYS[4], 'active_streams') or '')
if not active or active < 0 or active ~= math.floor(active)
then return {-2, 0} end
for _, field in ipairs({'profile', 'account', 'credential'}) do
  local key = redis.call('HGET', KEYS[3], field)
  if not key then return {-2, 0} end
  local count = tonumber(redis.call('GET', key) or '')
  if not count or count < 1 or count ~= math.floor(count)
  then return {-2, 0} end
end
return {1, redis.call('HINCRBY', KEYS[4], 'active_streams', 1)}
"""


_VOD_LEAVE = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'vod'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'm3u_profile_id') ~=
      redis.call('HGET', KEYS[3], 'profile_id')
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'content_uuid') ~= ARGV[4]
then return {0, 0} end
local active = tonumber(redis.call('HGET', KEYS[4], 'active_streams') or '')
if not active or active < 1 or active ~= math.floor(active)
then return {-2, 0} end
return {1, redis.call('HINCRBY', KEYS[4], 'active_streams', -1)}
"""


_VOD_CLEANUP = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return {-3, 0} end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'vod'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'm3u_profile_id') ~=
      redis.call('HGET', KEYS[3], 'profile_id')
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'content_uuid') ~= ARGV[4]
then return {0, 0} end
if redis.call('HGET', KEYS[4], 'active_streams') ~= '0'
then return {0, 0} end
for i = 5, 7 do
  local field = ({'profile', 'account', 'credential'})[i - 4]
  if redis.call('HGET', KEYS[3], field) ~= KEYS[i]
  then return {-2, 0} end
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count)
  then return {-2, 0} end
end
for i = 5, 7 do redis.call('DECR', KEYS[i]) end
redis.call('DEL', KEYS[4], KEYS[3], KEYS[2])
return {1, 0}
"""


_VOD_RESUME = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'vod'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[6]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[7]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'content_uuid') ~= ARGV[4]
   or redis.call('HGET', KEYS[4], 'm3u_profile_id') ~= ARGV[6]
then return 0 end
local active = tonumber(redis.call('HGET', KEYS[4], 'active_streams') or '')
if not active or active < 0 or active ~= math.floor(active)
then return -2 end
for i = 5, 7 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count)
  then return -2 end
end
return 1
"""


@dataclass(frozen=True, slots=True)
class VODSessionLease:
    """Internal cross-worker handle; never return its token to a viewer."""

    spec: ReservationSpec
    token: str
    session_id: str
    generation_id: str


def resume_vod_session(
    redis_client, *, session_id: str, user_id: int, content_uuid: str,
    spec_builder: Callable[[str], ReservationSpec],
) -> VODSessionLease | None:
    """Recover advisory handle, then atomically attest identity and counters.

    The trusted caller builds the expected spec from current provider policy.
    The session hash merely suggests token/generation; Lua grants authority.
    """
    _vod_viewer_identity(user_id, content_uuid)
    if not isinstance(session_id, str) or not session_id or "|" in session_id:
        raise ValueError("Invalid VOD session ID")
    if not callable(spec_builder):
        raise ValueError("A trusted VOD reservation policy is required")
    session_key = f"vod_persistent_connection:{session_id}"
    raw_token, raw_generation = redis_client.hmget(
        session_key, "atlas_reservation_token", "atlas_reservation_generation")
    if not raw_token or not raw_generation:
        return None
    token = raw_token.decode() if isinstance(raw_token, bytes) else raw_token
    generation = (raw_generation.decode() if isinstance(raw_generation, bytes)
                  else raw_generation)
    if (not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token)
        or not isinstance(generation, str)
        or not re.fullmatch(r"[0-9a-f]{32}", generation)):
        raise ReservationError("VOD session handle needs reconciliation")
    spec = spec_builder(generation)
    keys = (*_vod_keys(spec, token, session_id=session_id,
                       generation_id=generation), spec.profile_key,
            spec.account_key, spec.credential_key)
    result = int(redis_client.eval(_VOD_RESUME, len(keys), *keys, token,
                                   generation, user_id, content_uuid,
                                   spec.stream_id, spec.profile_id,
                                   spec.account_id))
    if result == 1:
        return VODSessionLease(spec, token, session_id, generation)
    if result == 0:
        return None
    raise ReservationError("VOD handoff or counters need reconciliation")


def bind_vod_session(redis_client, spec: ReservationSpec, token: str,
                     *, session_id: str, generation_id: str,
                     user_id: int, content_uuid: str) -> bool:
    """Bind an empty VOD session hash to one pending reservation atomically."""
    _vod_viewer_identity(user_id, content_uuid)
    keys = _vod_keys(spec, token, session_id=session_id,
                     generation_id=generation_id)
    result = int(redis_client.eval(_BIND_VOD, len(keys), *keys,
                                   token, generation_id, spec.profile_id,
                                   spec.stream_id, spec.account_id,
                                   user_id, content_uuid))
    if result == 1:
        return True
    if result == 0:
        return False
    raise ReservationError("VOD binding or counters need reconciliation")


def _vod_activity(redis_client, script: str, spec: ReservationSpec, token: str,
                  *, session_id: str, generation_id: str,
                  user_id: int, content_uuid: str) -> int | None:
    _vod_viewer_identity(user_id, content_uuid)
    keys = _vod_keys(spec, token, session_id=session_id,
                     generation_id=generation_id)
    result = redis_client.eval(script, len(keys), *keys, token, generation_id,
                               user_id, content_uuid)
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        raise ReservationError("Invalid VOD activity response")
    status, count = map(int, result)
    if status == 1 and count >= 0:
        return count
    if status == 0:
        return None
    raise ReservationError("VOD activity or counters need reconciliation")


def join_vod_session(redis_client, spec: ReservationSpec, token: str,
                     *, session_id: str, generation_id: str,
                     user_id: int, content_uuid: str) -> int | None:
    """Add one viewer to a token-matched VOD upstream session."""
    return _vod_activity(redis_client, _VOD_JOIN, spec, token,
                         session_id=session_id, generation_id=generation_id,
                         user_id=user_id, content_uuid=content_uuid)


def leave_vod_session(redis_client, spec: ReservationSpec, token: str,
                      *, session_id: str, generation_id: str,
                      user_id: int, content_uuid: str) -> int | None:
    """Remove one viewer, preserving upstream capacity until final cleanup."""
    return _vod_activity(redis_client, _VOD_LEAVE, spec, token,
                         session_id=session_id, generation_id=generation_id,
                         user_id=user_id, content_uuid=content_uuid)


def cleanup_vod_session(redis_client, spec: ReservationSpec, token: str,
                        *, session_id: str, generation_id: str,
                        user_id: int, content_uuid: str) -> bool:
    """Compare token, require zero viewers, and consume state/counters once."""
    _vod_viewer_identity(user_id, content_uuid)
    keys = (*_vod_keys(spec, token, session_id=session_id,
                       generation_id=generation_id), spec.profile_key,
            spec.account_key, spec.credential_key)
    result = redis_client.eval(_VOD_CLEANUP, len(keys), *keys,
                               token, generation_id, user_id, content_uuid)
    if not isinstance(result, (tuple, list)) or len(result) != 2:
        raise ReservationError("Invalid VOD cleanup response")
    status, _ = map(int, result)
    if status == 1:
        return True
    if status == 0:
        return False
    raise ReservationError("VOD cleanup or counters need reconciliation")


def _timeshift_keys(spec: ReservationSpec, token: str, *, session_id: str,
                    generation_id: str) -> tuple[str, ...]:
    if spec.mode != "timeshift":
        raise ValueError("Only timeshift reservations can bind a pool session")
    if (not isinstance(session_id, str) or not session_id
        or "|" in session_id or session_id != session_id.strip()
        or not isinstance(generation_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", generation_id)
        or spec.owner_id != f"{session_id}|{generation_id}"):
        raise ValueError("The timeshift session and generation must match its owner")
    return (CUTOVER_KEY, spec.owner_key, _record_key(token),
            f"timeshift:pool:{session_id}")


def _playback_id(playback_generation: str) -> str:
    if (not isinstance(playback_generation, str)
        or not re.fullmatch(r"[0-9a-f]{32}", playback_generation)):
        raise ValueError("A unique playback generation is required")
    return playback_generation


@dataclass(frozen=True, slots=True)
class TimeshiftPlaybackLease:
    """Internal callback handle; never expose token to a client."""

    spec: ReservationSpec
    token: str
    session_id: str
    generation_id: str
    playback_generation: str
    user_id: int

    def __post_init__(self) -> None:
        _timeshift_keys(self.spec, self.token, session_id=self.session_id,
                        generation_id=self.generation_id)
        _playback_id(self.playback_generation)
        if type(self.user_id) is not int or self.user_id < 1:
            raise ValueError("An authenticated timeshift user is required")


_BIND_TIMESHIFT = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1] then return 0 end
if redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'timeshift'
   or redis.call('HGET', KEYS[3], 'state') ~= 'pending'
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[6]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[7]
then return -2 end
if redis.call('EXISTS', KEYS[4]) ~= 1
   or redis.call('HGET', KEYS[4], 'busy') ~= '1'
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[4], 'dispatcharr_stream_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[4], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[4], 'account_id') ~= ARGV[7]
   or redis.call('HEXISTS', KEYS[4], 'atlas_reservation_token') ~= 0
   or redis.call('HEXISTS', KEYS[4], 'atlas_reservation_generation') ~= 0
then return 0 end
for i = 5, 7 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count) then return -2 end
end
redis.call('HSET', KEYS[4], 'atlas_reservation_token', ARGV[1],
           'atlas_reservation_generation', ARGV[2],
           'atlas_playback_generation', ARGV[3])
redis.call('HSET', KEYS[3], 'state', 'active')
return 1
"""


_CLAIM_TIMESHIFT = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'timeshift'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[6]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[7]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[4], 'dispatcharr_stream_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[4], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[4], 'account_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[4], 'busy') ~= '0'
   or redis.call('HGET', KEYS[4], 'atlas_playback_generation') == ARGV[3]
then return 0 end
for i = 5, 7 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count) then return -2 end
end
redis.call('HSET', KEYS[4], 'busy', '1',
           'atlas_playback_generation', ARGV[3])
redis.call('HDEL', KEYS[4], 'atlas_stopped_generation')
return 1
"""


_IDLE_TIMESHIFT = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'timeshift'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[6]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[7]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'atlas_playback_generation') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[4], 'dispatcharr_stream_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[4], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[4], 'account_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[4], 'busy') ~= '1'
then return 0 end
for i = 5, 7 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count) then return -2 end
end
redis.call('HSET', KEYS[4], 'busy', '0')
redis.call('HDEL', KEYS[4], 'atlas_stopped_generation')
return 1
"""


_ACK_TIMESHIFT_STOP = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'timeshift'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'atlas_playback_generation') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[4], 'busy') ~= '1'
then return 0 end
redis.call('HSET', KEYS[4], 'atlas_stopped_generation', ARGV[3])
return 1
"""


_RESUME_TIMESHIFT = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'timeshift'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[6]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[7]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'atlas_playback_generation') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[4], 'dispatcharr_stream_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[4], 'profile_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[4], 'account_id') ~= ARGV[7]
   or (redis.call('HGET', KEYS[4], 'busy') ~= '0'
       and redis.call('HGET', KEYS[4], 'busy') ~= '1')
then return 0 end
for i = 5, 7 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  local limit = tonumber(ARGV[i + 3])
  if not count or count < 1 or count ~= math.floor(count)
     or not limit or count > limit then return -2 end
end
return 1
"""


_SUPERSEDE_TIMESHIFT = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'timeshift'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[6]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[8]
   or redis.call('HGET', KEYS[3], 'profile') ~= KEYS[5]
   or redis.call('HGET', KEYS[3], 'account') ~= KEYS[6]
   or redis.call('HGET', KEYS[3], 'credential') ~= KEYS[7]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'atlas_playback_generation') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'atlas_stopped_generation') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[4], 'dispatcharr_stream_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[4], 'profile_id') ~= ARGV[7]
   or redis.call('HGET', KEYS[4], 'account_id') ~= ARGV[8]
   or redis.call('HGET', KEYS[4], 'busy') ~= '1'
   or ARGV[3] == ARGV[4]
then return 0 end
for i = 5, 7 do
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count) then return -2 end
end
redis.call('HSET', KEYS[4], 'atlas_playback_generation', ARGV[4])
redis.call('HDEL', KEYS[4], 'atlas_stopped_generation')
return 1
"""


_CLEANUP_TIMESHIFT = """
if redis.call('GET', KEYS[1]) ~= 'ledger' then return -3 end
if redis.call('GET', KEYS[2]) ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'token') ~= ARGV[1]
   or redis.call('HGET', KEYS[3], 'owner') ~= KEYS[2]
   or redis.call('HGET', KEYS[3], 'mode') ~= 'timeshift'
   or redis.call('HGET', KEYS[3], 'state') ~= 'active'
   or redis.call('HGET', KEYS[3], 'stream') ~= ARGV[4]
   or redis.call('HGET', KEYS[3], 'profile_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[3], 'account_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_token') ~= ARGV[1]
   or redis.call('HGET', KEYS[4], 'atlas_reservation_generation') ~= ARGV[2]
   or redis.call('HGET', KEYS[4], 'user_id') ~= ARGV[3]
   or redis.call('HGET', KEYS[4], 'dispatcharr_stream_id') ~= ARGV[4]
   or redis.call('HGET', KEYS[4], 'profile_id') ~= ARGV[5]
   or redis.call('HGET', KEYS[4], 'account_id') ~= ARGV[6]
   or redis.call('HGET', KEYS[4], 'busy') ~= '0'
then return 0 end
for i = 5, 7 do
  local field = ({'profile', 'account', 'credential'})[i - 4]
  if redis.call('HGET', KEYS[3], field) ~= KEYS[i]
  then return -2 end
  local count = tonumber(redis.call('GET', KEYS[i]) or '')
  if not count or count < 1 or count ~= math.floor(count)
  then return -2 end
end
for i = 5, 7 do redis.call('DECR', KEYS[i]) end
redis.call('DEL', KEYS[4], KEYS[3], KEYS[2])
return 1
"""


def _timeshift_eval(redis_client, script: str, spec: ReservationSpec,
                    token: str, *, session_id: str, generation_id: str,
                    user_id: int, playback_generation: str | None = None) -> bool:
    if type(user_id) is not int or user_id < 1:
        raise ValueError("An authenticated timeshift user is required")
    keys = (*_timeshift_keys(spec, token, session_id=session_id,
                            generation_id=generation_id), spec.profile_key,
            spec.account_key, spec.credential_key)
    arguments = [token, generation_id]
    if playback_generation is not None:
        arguments.append(_playback_id(playback_generation))
    arguments.append(user_id)
    arguments.extend((spec.stream_id, spec.profile_id, spec.account_id))
    result = int(redis_client.eval(script, len(keys), *keys, *arguments))
    if result == 1:
        return True
    if result == 0:
        return False
    raise ReservationError("Timeshift session or counters need reconciliation")


def bind_timeshift_pool(redis_client, spec: ReservationSpec, token: str,
                        *, session_id: str, generation_id: str,
                        playback_generation: str, user_id: int) -> bool:
    """Bind the initial busy pool session to one pending reservation."""
    return _timeshift_eval(redis_client, _BIND_TIMESHIFT, spec, token,
        session_id=session_id, generation_id=generation_id,
        playback_generation=playback_generation, user_id=user_id)


def claim_timeshift_idle_pool(redis_client, spec: ReservationSpec, token: str,
                              *, session_id: str, generation_id: str,
                              playback_generation: str, user_id: int) -> bool:
    """Start a new playback on an idle, still-reserved pool session."""
    return _timeshift_eval(redis_client, _CLAIM_TIMESHIFT, spec, token,
        session_id=session_id, generation_id=generation_id,
        playback_generation=playback_generation, user_id=user_id)


def idle_timeshift_pool(redis_client, spec: ReservationSpec, token: str,
                        *, session_id: str, generation_id: str,
                        playback_generation: str, user_id: int) -> bool:
    """Only the current playback may return the pool to idle."""
    return _timeshift_eval(redis_client, _IDLE_TIMESHIFT, spec, token,
        session_id=session_id, generation_id=generation_id,
        playback_generation=playback_generation, user_id=user_id)


def supersede_timeshift_busy_pool(
    redis_client, spec: ReservationSpec, token: str, *, session_id: str,
    generation_id: str, previous_playback_generation: str,
    new_playback_generation: str, user_id: int,
) -> bool:
    """Fence an old busy playback after its upstream has been stopped.

    The caller must independently prove the displaced upstream socket ended.
    This atomic swap itself cannot authorize a second provider connection.
    """
    if type(user_id) is not int or user_id < 1:
        raise ValueError("An authenticated timeshift user is required")
    keys = (*_timeshift_keys(spec, token, session_id=session_id,
                            generation_id=generation_id), spec.profile_key,
            spec.account_key, spec.credential_key)
    result = int(redis_client.eval(_SUPERSEDE_TIMESHIFT, len(keys), *keys,
        token, generation_id, _playback_id(previous_playback_generation),
        _playback_id(new_playback_generation), user_id, spec.stream_id,
        spec.profile_id, spec.account_id))
    if result == 1:
        return True
    if result == 0:
        return False
    raise ReservationError("Timeshift handoff or counters need reconciliation")


def ack_timeshift_upstream_stopped(
    redis_client, spec: ReservationSpec, token: str, *, session_id: str,
    generation_id: str, playback_generation: str, user_id: int,
) -> bool:
    """Record a caller attestation only after its upstream socket closed.

    This cannot be called merely because a stop was requested or timed out.
    """
    if type(user_id) is not int or user_id < 1:
        raise ValueError("An authenticated timeshift user is required")
    keys = _timeshift_keys(spec, token, session_id=session_id,
                           generation_id=generation_id)
    result = int(redis_client.eval(_ACK_TIMESHIFT_STOP, len(keys), *keys,
        token, generation_id, _playback_id(playback_generation), user_id))
    if result == 1:
        return True
    if result == 0:
        return False
    raise ReservationError("Timeshift stop attestation needs reconciliation")


def resume_timeshift_pool(
    redis_client, *, session_id: str, user_id: int,
    spec_builder: Callable[[str], ReservationSpec],
) -> TimeshiftPlaybackLease | None:
    """Attest a cross-worker pool handle against trusted current policy.

    Pool fields are advisory. The caller must rebuild the expected account,
    stream, credential realm and bounded capacities independently. Lua checks
    that expected identity, authenticated user, token and live counters.
    """
    if type(user_id) is not int or user_id < 1:
        raise ValueError("An authenticated timeshift user is required")
    if (not isinstance(session_id, str) or not session_id
        or "|" in session_id or session_id != session_id.strip()):
        raise ValueError("Invalid timeshift session ID")
    if not callable(spec_builder):
        raise ValueError("A trusted timeshift reservation policy is required")
    raw = redis_client.hmget(f"timeshift:pool:{session_id}",
        "atlas_reservation_token", "atlas_reservation_generation",
        "atlas_playback_generation")
    if not all(raw):
        return None
    token, generation, playback = (
        value.decode() if isinstance(value, bytes) else value for value in raw)
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value)
           for value in (token, generation, playback)):
        raise ReservationError("Timeshift pool handle needs reconciliation")
    expected = spec_builder(generation)
    keys = (*_timeshift_keys(expected, token, session_id=session_id,
                            generation_id=generation), expected.profile_key,
            expected.account_key, expected.credential_key)
    result = int(redis_client.eval(_RESUME_TIMESHIFT, len(keys), *keys,
        token, generation, playback, user_id, expected.stream_id,
        expected.profile_id, expected.account_id, expected.profile_capacity,
        expected.account_capacity, expected.credential_capacity))
    if result == 1:
        return TimeshiftPlaybackLease(expected, token, session_id,
                                      generation, playback, user_id)
    if result == 0:
        return None
    raise ReservationError("Timeshift pool or counters need reconciliation")


def cleanup_timeshift_pool(redis_client, spec: ReservationSpec, token: str,
                           *, session_id: str, generation_id: str,
                           user_id: int) -> bool:
    """Atomically release the idle pool session and all capacity counters."""
    return _timeshift_eval(redis_client, _CLEANUP_TIMESHIFT, spec, token,
        session_id=session_id, generation_id=generation_id,
        user_id=user_id)


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"Invalid {name}")
    return value


def activate_verified_live(redis_client, spec: ReservationSpec, token: str,
                           *, channel_id: str, worker_id: str,
                           grant_token: str, grant_epoch: int,
                           generation_id: str, chunk_index: int) -> bool:
    """Promote pending capacity only after an owner-bound raw TS chunk exists.

    This is an isolated primitive. No Dispatcharr caller currently invokes it.
    """
    if type(grant_epoch) is not int or grant_epoch < 1:
        raise ValueError("Invalid verified epoch")
    keys = _live_keys(spec, token, channel_id=channel_id,
                      worker_id=worker_id, chunk_index=chunk_index)
    result = int(redis_client.eval(_ACTIVATE_LIVE, len(keys), *keys,
        token, _required_text(grant_token, "grant token"),
        str(grant_epoch), _required_text(generation_id, "generation ID"),
        worker_id))
    if result == 1:
        return True
    if result == 0:
        return False
    raise ReservationError("Live attestation or counters need reconciliation")


def attest_live_join(redis_client, spec: ReservationSpec, token: str,
                     *, channel_id: str, worker_id: str,
                     grant_epoch: int, generation_id: str,
                     chunk_index: int) -> tuple[int, int, int] | None:
    """Read-only join: return stream/profile/account IDs without incrementing."""
    if type(grant_epoch) is not int or grant_epoch < 1:
        raise ValueError("Invalid verified epoch")
    keys = _live_keys(spec, token, channel_id=channel_id,
                      worker_id=worker_id, chunk_index=chunk_index)
    keys = (*keys, spec.profile_key, spec.account_key, spec.credential_key)
    result = redis_client.eval(_ATTEST_LIVE_JOIN, len(keys), *keys,
        token, str(grant_epoch), _required_text(generation_id, "generation ID"),
        spec.profile_capacity, spec.account_capacity, spec.credential_capacity)
    if not isinstance(result, (list, tuple)) or not result:
        raise ReservationError("Invalid live join response")
    try:
        status = int(result[0])
        if status == 1 and len(result) == 4:
            ids = tuple(int(value) for value in result[1:])
            if all(value > 0 for value in ids):
                return ids
    except (TypeError, ValueError) as exc:
        raise ReservationError("Invalid live join response") from exc
    if status == 0 and len(result) == 1:
        return None
    raise ReservationError("Live join attestation or counters need reconciliation")


def attest_current_live_channel(
    redis_client, *, channel_id: str, chunk_index: int,
    spec_builder: Callable[[int, int, int, str], ReservationSpec],
    expected_grant_epoch: int | None = None,
    expected_generation_id: str | None = None,
) -> tuple[int, int, int] | None:
    """Rebuild trusted policy and attest the current channel for a viewer.

    Redis alias/grant reads are advisory. `attest_live_join` uses one Lua call
    to recheck them with the exact owner lease, raw chunk provenance, and
    capacity counters. No viewer supplies a token, credential scope, or policy.
    """
    if (not isinstance(channel_id, str)
        or str(UUID(channel_id)) != channel_id
        or type(chunk_index) is not int or chunk_index < 1
        or not callable(spec_builder)):
        raise ValueError("A channel, raw index, and trusted policy are required")
    if ((expected_grant_epoch is None) != (expected_generation_id is None)):
        raise ValueError("The reader epoch and generation must be paired")
    if expected_grant_epoch is not None and (
        type(expected_grant_epoch) is not int or expected_grant_epoch < 1
        or not isinstance(expected_generation_id, str)
        or not expected_generation_id
    ):
        raise ValueError("Invalid reader generation")
    alias = redis_client.hgetall(
        f"atlas:reservation:v1:live:channel:{channel_id}"
    )
    if not alias:
        return None
    grant = redis_client.hgetall(
        f"atlas:dispatcharr:attestation:{channel_id}:grant"
    )
    if not grant:
        return None

    def field(row, name):
        value = row.get(name.encode(), row.get(name))
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ReservationError("Invalid live identity") from None
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ReservationError("Invalid live identity")
        return value

    token = field(alias, "token")
    lease = field(alias, "owner_lease")
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ReservationError("Invalid live token")
    try:
        stream_id = int(field(alias, "stream_id"))
        profile_id = int(field(alias, "profile_id"))
        account_id = int(field(alias, "account_id"))
        epoch = int(field(grant, "epoch"))
    except ValueError:
        raise ReservationError("Invalid live selected identity") from None
    if min(stream_id, profile_id, account_id, epoch) < 1:
        raise ReservationError("Invalid live selected identity")
    if field(grant, "worker") != lease:
        return None
    generation = redis_client.get(
        f"atlas:dispatcharr:attestation:{channel_id}:generation"
    )
    if isinstance(generation, bytes):
        try:
            generation = generation.decode("utf-8")
        except UnicodeDecodeError:
            raise ReservationError("Invalid live generation") from None
    if not isinstance(generation, str) or not generation or len(generation) > 256:
        return None
    if expected_grant_epoch is not None and (
        epoch != expected_grant_epoch
        or generation != expected_generation_id
    ):
        return None
    expected = spec_builder(stream_id, profile_id, account_id, lease)
    if (not isinstance(expected, ReservationSpec)
        or expected.mode != "live"
        or expected.owner_id != f"{channel_id}|{lease}"
        or (expected.stream_id, expected.profile_id, expected.account_id)
           != (stream_id, profile_id, account_id)):
        raise ReservationError("Trusted live policy identity changed")
    return attest_live_join(redis_client, expected, token,
        channel_id=channel_id, worker_id=lease, grant_epoch=epoch,
        generation_id=generation, chunk_index=chunk_index)


def _owner_key(mode: str, owner_id: str) -> str:
    if mode not in {"live", "vod", "timeshift"} or not owner_id:
        raise ValueError("Invalid reservation owner")
    digest = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()
    return f"atlas:reservation:v1:owner:{mode}:{digest}"


def _current_counter_keys(redis_client, *, mode: str,
                          owner_id: str, token: str) -> tuple[str, str, str] | None:
    """Read advisory key names; the subsequent Lua script rechecks all of them."""
    record = redis_client.hgetall(_record_key(token))
    if not isinstance(record, dict):
        raise ReservationError("Reservation record is unavailable")
    if not record:
        owner_value = redis_client.get(_owner_key(mode, owner_id))
        if owner_value in (token, token.encode()):
            raise ReservationError("Reservation owner points to a missing record")
        return None
    fields = {
        (key.decode() if isinstance(key, bytes) else key):
        (value.decode() if isinstance(value, bytes) else value)
        for key, value in record.items()
    }
    if (fields.get("token") != token
        or fields.get("owner") != _owner_key(mode, owner_id)):
        raise ReservationBusy("Reservation owner changed")
    keys = (fields.get("profile"), fields.get("account"),
            fields.get("credential"))
    patterns = (r"profile_connections:[1-9][0-9]*\Z",
                r"atlas:reservation:v1:account:[1-9][0-9]*\Z",
                r"atlas:reservation:v1:credential:[0-9a-f]{64}\Z")
    if any(not isinstance(key, str) or not re.fullmatch(pattern, key)
           for key, pattern in zip(keys, patterns)):
        raise ReservationError("Reservation counter identity is invalid")
    return keys


def _outcome(result, *, conflict: str) -> int:
    if not isinstance(result, (list, tuple)) or len(result) != 2:
        raise ReservationError("Invalid Redis reservation response")
    try:
        status, count = map(int, result)
    except (ValueError, TypeError) as exc:
        raise ReservationError("Invalid Redis reservation response") from exc
    if status == 1:
        return count
    if status == 0:
        raise ReservationBusy(conflict)
    if status == -1:
        raise ReservationFull("Verified upstream capacity is full")
    raise ReservationError("Reservation cutover or counters need reconciliation")


def reserve(redis_client, spec: ReservationSpec) -> tuple[str, int]:
    """Allocate a pending upstream reservation in a single Redis script."""
    token = uuid.uuid4().hex
    count = _outcome(redis_client.eval(_RESERVE, 6,
        CUTOVER_KEY, spec.owner_key, _record_key(token), spec.profile_key,
        spec.account_key, spec.credential_key,
        token, spec.profile_capacity, spec.account_capacity,
        spec.credential_capacity, spec.stream_id, spec.mode,
        spec.profile_id, spec.account_id),
        conflict="Owner is already reserved")
    return token, count


def _live_channel_reservation_keys(
    spec: ReservationSpec, token: str, *, channel_id: str,
    owner_lease: str,
) -> tuple[str, ...]:
    if (spec.mode != "live" or not isinstance(channel_id, str)
        or str(UUID(channel_id)) != channel_id
        or not isinstance(owner_lease, str) or not owner_lease.strip()
        or spec.owner_id != f"{channel_id}|{owner_lease}"):
        raise ValueError("The live channel and owner lease must match")
    return (CUTOVER_KEY, spec.owner_key, _record_key(token),
            spec.profile_key, spec.account_key, spec.credential_key,
            f"atlas:reservation:v1:live:channel:{channel_id}",
            f"live:channel:{channel_id}:owner")


def reserve_live_channel(
    redis_client, spec: ReservationSpec, *, channel_id: str,
    owner_lease: str,
) -> tuple[str, int]:
    """Atomically reserve capacity and bind one channel owner alias.

    Only the verified proxy owner may pass the lease; a viewer never receives
    the token. An existing alias must be reconciled, not overwritten.
    """
    token = uuid.uuid4().hex
    keys = _live_channel_reservation_keys(spec, token, channel_id=channel_id,
                                          owner_lease=owner_lease)
    count = _outcome(redis_client.eval(_RESERVE_LIVE_CHANNEL, len(keys), *keys,
        token, spec.profile_capacity, spec.account_capacity,
        spec.credential_capacity, spec.stream_id, "live", spec.profile_id,
        spec.account_id, owner_lease),
        conflict="Live channel owner or assignment already exists")
    return token, count


def release_pending_live_channel(
    redis_client, spec: ReservationSpec, token: str, *, channel_id: str,
    owner_lease: str,
) -> bool:
    """Roll back only this owner's still-pending acquisition atomically.

    An active upstream needs a separate close attestation and final release;
    this method cannot clear an active grant or a replacement owner's slot.
    """
    keys = _live_channel_reservation_keys(spec, token, channel_id=channel_id,
                                          owner_lease=owner_lease)
    try:
        _outcome(redis_client.eval(_RELEASE_PENDING_LIVE_CHANNEL, len(keys),
            *keys, token, owner_lease, spec.stream_id, spec.profile_id,
            spec.account_id),
            conflict="Pending live assignment was replaced or activated")
    except ReservationBusy:
        return False
    return True


def _active_live_channel_keys(
    spec: ReservationSpec, token: str, *, channel_id: str,
    owner_lease: str,
) -> tuple[str, ...]:
    first = _live_channel_reservation_keys(spec, token, channel_id=channel_id,
                                           owner_lease=owner_lease)
    prefix = f"atlas:dispatcharr:attestation:{channel_id}"
    return (*first, prefix + ":grant", prefix + ":generation")


def _active_live_arguments(
    spec: ReservationSpec, token: str, owner_lease: str,
    grant_token: str, grant_epoch: int, generation_id: str,
) -> tuple[object, ...]:
    if type(grant_epoch) is not int or grant_epoch < 1:
        raise ValueError("Invalid verified epoch")
    return (token, owner_lease, spec.stream_id, spec.profile_id,
            spec.account_id, _required_text(grant_token, "grant token"),
            str(grant_epoch), _required_text(generation_id, "generation ID"))


def mark_live_upstream_closed(
    redis_client, spec: ReservationSpec, token: str, *, channel_id: str,
    owner_lease: str, grant_token: str, grant_epoch: int,
    generation_id: str, upstream_closed: bool,
) -> bool:
    """Trusted socket owner attests completed close, not just a stop request."""
    if upstream_closed is not True:
        raise ValueError("Upstream socket closure must be confirmed")
    keys = _active_live_channel_keys(spec, token, channel_id=channel_id,
                                     owner_lease=owner_lease)
    args = _active_live_arguments(spec, token, owner_lease, grant_token,
                                  grant_epoch, generation_id)
    result = int(redis_client.eval(_ACK_LIVE_STOP, len(keys), *keys, *args))
    if result == 1:
        return True
    if result == 0:
        return False
    raise ReservationError("Live upstream stop needs reconciliation")


def release_active_live_channel(
    redis_client, spec: ReservationSpec, token: str, *, channel_id: str,
    owner_lease: str, grant_token: str, grant_epoch: int,
    generation_id: str,
) -> bool:
    """Consume one active reservation only after its matching stop attestation."""
    keys = _active_live_channel_keys(spec, token, channel_id=channel_id,
                                     owner_lease=owner_lease)
    args = _active_live_arguments(spec, token, owner_lease, grant_token,
                                  grant_epoch, generation_id)
    result = int(redis_client.eval(_RELEASE_ACTIVE_LIVE, len(keys), *keys, *args))
    if result == 1:
        return True
    if result == 0:
        return False
    raise ReservationError("Live channel or counters need reconciliation")


def switch_live_channel(
    redis_client, previous: ReservationSpec, destination: ReservationSpec,
    token: str, *, channel_id: str, owner_lease: str,
    stopped_grant_token: str | None = None,
    stopped_grant_epoch: int | None = None,
    stopped_generation_id: str | None = None,
) -> int:
    """Move a channel alias and its counters after a confirmed active stop.

    All three stop identity arguments are required for an active channel and
    must be omitted together for a pending channel. Lua enforces the state.
    """
    if previous.mode != "live" or destination.mode != "live":
        raise ValueError("A live channel switch requires live reservations")
    if previous.owner_id != destination.owner_id:
        raise ValueError("A switch cannot change the channel owner lifecycle")
    old = _live_channel_reservation_keys(previous, token,
        channel_id=channel_id, owner_lease=owner_lease)
    if (stopped_grant_token is None and stopped_grant_epoch is None
        and stopped_generation_id is None):
        grant_token = epoch = generation = ""
    else:
        if type(stopped_grant_epoch) is not int or stopped_grant_epoch < 1:
            raise ValueError("Invalid stopped grant epoch")
        grant_token = _required_text(stopped_grant_token, "stopped grant token")
        epoch = str(stopped_grant_epoch)
        generation = _required_text(stopped_generation_id,
                                    "stopped generation ID")
    keys = (CUTOVER_KEY, previous.owner_key, _record_key(token),
            previous.profile_key, previous.account_key,
            previous.credential_key, destination.profile_key,
            destination.account_key, destination.credential_key,
            old[6], old[7],
            f"atlas:dispatcharr:attestation:{channel_id}:grant",
            f"atlas:dispatcharr:attestation:{channel_id}:generation")
    return _outcome(redis_client.eval(_SWITCH_LIVE_CHANNEL, len(keys), *keys,
        token, owner_lease, destination.profile_capacity,
        destination.account_capacity, destination.credential_capacity,
        destination.stream_id, destination.profile_id, destination.account_id,
        grant_token, epoch, generation),
        conflict="Channel owner or stopped generation changed")


def release(redis_client, spec: ReservationSpec, token: str) -> bool:
    """Consume exactly the bound token; a stale or duplicate release is a no-op."""
    try:
        _outcome(redis_client.eval(_RELEASE, 6,
            CUTOVER_KEY, spec.owner_key, _record_key(token), spec.profile_key,
            spec.account_key, spec.credential_key, token),
            conflict="Reservation was already released or replaced")
    except ReservationBusy:
        return False
    return True


def release_current(redis_client, *, mode: Literal["live", "vod", "timeshift"],
                    owner_id: str, token: str) -> bool:
    """Release after a switch or handoff using the persisted identity.

    HGETALL is not authority. Lua compares the exact record, owner alias, and
    current counters again, so a concurrent switch or replacement fails closed.
    """
    keys = _current_counter_keys(
        redis_client, mode=mode, owner_id=owner_id, token=token)
    if keys is None:
        return False
    profile_key, account_key, credential_key = keys
    try:
        _outcome(redis_client.eval(_RELEASE, 6, CUTOVER_KEY,
            _owner_key(mode, owner_id), _record_key(token), profile_key,
            account_key, credential_key, token),
            conflict="Reservation was already released or replaced")
    except ReservationBusy:
        return False
    return True


def switch_current(redis_client, *, destination: ReservationSpec,
                   token: str) -> int:
    """Switch after handoff, with old counter keys revalidated in Lua."""
    keys = _current_counter_keys(
        redis_client, mode=destination.mode,
        owner_id=destination.owner_id, token=token)
    if keys is None:
        raise ReservationBusy("Reservation was already released or replaced")
    profile_key, account_key, credential_key = keys
    return _outcome(redis_client.eval(_SWITCH, 9, CUTOVER_KEY,
        destination.owner_key, _record_key(token), profile_key,
        account_key, credential_key, destination.profile_key,
        destination.account_key, destination.credential_key,
        token, destination.profile_capacity, destination.account_capacity,
        destination.credential_capacity, destination.stream_id,
        destination.profile_id, destination.account_id),
        conflict="Reservation owner changed")


def switch(redis_client, previous: ReservationSpec,
           destination: ReservationSpec, token: str) -> int:
    """Move one reservation atomically while preserving owner and token."""
    if (previous.mode, previous.owner_id) != (destination.mode, destination.owner_id):
        raise ValueError("A reservation switch cannot change owner lifecycle")
    return _outcome(redis_client.eval(_SWITCH, 9,
        CUTOVER_KEY, previous.owner_key, _record_key(token),
        previous.profile_key, previous.account_key, previous.credential_key,
        destination.profile_key, destination.account_key,
        destination.credential_key, token, destination.profile_capacity,
        destination.account_capacity, destination.credential_capacity,
        destination.stream_id, destination.profile_id,
        destination.account_id), conflict="Reservation owner changed")
