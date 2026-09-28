"""Fail-closed policy assembly for a future trusted Atlas live adapter.

This module cannot authenticate a binding or an observation by itself. Only a
server-side adapter with authoritative Atlas source state and provider status
may construct the inputs. Neither request parameters nor Redis aliases are
acceptable sources. No production caller installs this policy yet.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from dataclasses import dataclass
from uuid import UUID

from apps.m3u.reservation_ledger import ReservationSpec


class VerifiedLivePolicyUnavailable(RuntimeError):
    """A source identity or current provider limit cannot be established."""


@dataclass(frozen=True, slots=True, repr=False)
class TrustedSourceBinding:
    source_id: str
    channel_id: str
    account_id: int
    profile_id: int
    canonical_realm: str
    configured_max_connections: int
    enabled: bool


@dataclass(frozen=True, slots=True, repr=False)
class TrustedCapacityObservation:
    account_id: int
    canonical_realm: str
    status: str
    provider_max_connections: int
    observed_at_unix: int


def _positive(value) -> bool:
    return type(value) is int and value > 0


def build_verified_live_spec(
    *, channel_id: str, owner_lease: str, stream, profile, account,
    binding: TrustedSourceBinding, observation: TrustedCapacityObservation,
    event_resource_source_ids: frozenset[str],
    transformed_username: str, transformed_password: str,
    scope_key: bytes, now_unix: int | None = None,
) -> ReservationSpec:
    """Bind effective playback credentials to observed provider capacity.

    The event resource IDs must come from the trusted live-source catalogue;
    membership prevents assigning a valid account to an unrelated event.
    A canonical realm intentionally groups one login across alternate provider
    origins. The server-held HMAC key keeps Redis counter names opaque. This
    function makes no provider call and does not decide whether its inputs are
    authoritative; the calling adapter must establish that independently.
    """
    try:
        valid_channel = isinstance(channel_id, str) and str(UUID(channel_id)) == channel_id
    except (ValueError, AttributeError):
        valid_channel = False
    if (not valid_channel
        or not isinstance(owner_lease, str)
        or not owner_lease.strip()):
        raise VerifiedLivePolicyUnavailable("Invalid channel owner")
    if (not isinstance(binding, TrustedSourceBinding)
        or not isinstance(observation, TrustedCapacityObservation)
        or binding.enabled is not True
        or not isinstance(binding.source_id, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", binding.source_id)
        or binding.channel_id != channel_id
        or not isinstance(event_resource_source_ids, frozenset)
        or binding.source_id not in event_resource_source_ids
        or not isinstance(binding.canonical_realm, str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,127}", binding.canonical_realm)
        or binding.canonical_realm != observation.canonical_realm
        or observation.status != "active"):
        raise VerifiedLivePolicyUnavailable("Provider authority is unavailable")
    if (not _positive(getattr(stream, "id", None))
        or not _positive(getattr(profile, "id", None))
        or not _positive(getattr(account, "id", None))
        or account.account_type != "XC"
        or account.is_active is not True
        or stream.m3u_account_id != account.id
        or profile.m3u_account_id != account.id
        or binding.account_id != account.id
        or binding.profile_id != profile.id
        or observation.account_id != account.id):
        raise VerifiedLivePolicyUnavailable("Selected account identity changed")
    if any(not _positive(value) for value in (
        binding.configured_max_connections,
        observation.provider_max_connections,
        account.max_streams,
        profile.max_streams,
    )):
        raise VerifiedLivePolicyUnavailable("Unbounded provider capacity")

    now = int(time.time()) if now_unix is None else now_unix
    if (type(now) is not int or not _positive(observation.observed_at_unix)
        or observation.observed_at_unix > now
        or now - observation.observed_at_unix > 300):
        raise VerifiedLivePolicyUnavailable("Provider capacity evidence expired")
    if (not isinstance(transformed_username, str)
        or not transformed_username.strip()
        or not isinstance(transformed_password, str)
        or not transformed_password
        or not isinstance(scope_key, bytes)
        or len(scope_key) < 32):
        raise VerifiedLivePolicyUnavailable("Playback identity is unavailable")

    capacity = min(binding.configured_max_connections,
                   observation.provider_max_connections)
    profile_capacity = min(profile.max_streams, capacity)
    account_capacity = min(account.max_streams, capacity)
    # The realm is an authoritative provider namespace; profiles using the
    # same transformed login share one credential counter under this realm.
    payload = "\0".join((binding.canonical_realm, transformed_username,
                         transformed_password)).encode("utf-8")
    credential_scope = hmac.new(scope_key, payload, hashlib.sha256).hexdigest()
    return ReservationSpec(
        mode="live", owner_id=f"{channel_id}|{owner_lease}",
        stream_id=stream.id, profile_id=profile.id, account_id=account.id,
        credential_scope=credential_scope,
        profile_capacity=profile_capacity, account_capacity=account_capacity,
        credential_capacity=capacity,
    )
