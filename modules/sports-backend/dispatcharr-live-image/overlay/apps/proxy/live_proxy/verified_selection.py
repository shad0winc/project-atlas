"""Owner-only channel selection for a future verified live caller.

No production entry point calls this module. The caller must supply a trusted
policy resolver; neither viewer data nor account settings alone authorize a
provider reservation. A pending handle must be rolled back on failed setup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from apps.m3u.reservation_ledger import (
    ReservationBusy,
    ReservationFull,
    ReservationSpec,
    release_pending_live_channel,
    reserve_live_channel,
)
from apps.m3u.verified_live_plan import VerifiedLivePlan


class VerifiedSelectionError(RuntimeError):
    """Selection cannot safely start another upstream connection."""


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedLiveSelection:
    channel_id: str
    owner_lease: str
    spec: ReservationSpec
    token: str
    stream_url: str
    user_agent: str
    transcode: bool
    output_profile_id: int

    @property
    def stream_id(self) -> int:
        return self.spec.stream_id

    @property
    def profile_id(self) -> int:
        return self.spec.profile_id

    @property
    def account_id(self) -> int:
        return self.spec.account_id

    def rollback_pending(self, redis_client) -> bool:
        """Consume only this token's pending capacity and channel alias."""
        return release_pending_live_channel(
            redis_client, self.spec, self.token,
            channel_id=self.channel_id, owner_lease=self.owner_lease,
        )


def select_verified_channel(
    redis_client,
    *,
    channel,
    owner_lease: str,
    policy: Callable,
) -> VerifiedLiveSelection:
    """Select one eligible candidate and atomically reserve its channel slot.

    `policy(channel, stream, profile, account, owner_lease)` must return a
    private VerifiedLivePlan. Its spec and URL must derive from the same
    strict effective credential tuple. The URL remains internal and is omitted
    from the handle's representation.
    """
    channel_id = str(channel.uuid)
    if str(UUID(channel_id)) != channel_id:
        raise ValueError("A canonical channel UUID is required")
    if not isinstance(owner_lease, str) or not owner_lease.strip():
        raise ValueError("A unique verified owner lease is required")
    if not callable(policy):
        raise ValueError("Trusted policy is required")
    if redis_client is None:
        raise VerifiedSelectionError("Verified Redis is unavailable")

    output_profile = channel.get_stream_profile()
    if output_profile is None or type(output_profile.id) is not int:
        raise VerifiedSelectionError("Output profile is unavailable")
    if output_profile.is_redirect() or not output_profile.is_proxy():
        raise VerifiedSelectionError("Verified sharing requires a TS proxy input")

    at_capacity = False
    for stream in channel.streams.all().order_by("channelstream__order"):
        account = stream.m3u_account
        if account is None or not account.is_active:
            continue
        profiles = list(account.profiles.filter(is_active=True))
        defaults = [profile for profile in profiles if profile.is_default]
        if len(defaults) != 1:
            raise VerifiedSelectionError("Default provider profile is ambiguous")
        candidates = defaults + [profile for profile in profiles if not profile.is_default]
        for profile in candidates:
            plan = policy(channel, stream, profile, account, owner_lease)
            if not isinstance(plan, VerifiedLivePlan):
                raise VerifiedSelectionError("Verified provider plan unavailable")
            spec = plan.spec
            if not isinstance(spec, ReservationSpec) or (
                spec.mode != "live"
                or spec.owner_id != f"{channel_id}|{owner_lease}"
                or spec.stream_id != stream.id
                or spec.profile_id != profile.id
                or spec.account_id != account.id
            ):
                raise VerifiedSelectionError("Verified provider identity changed")
            if not isinstance(plan.upstream_url, str) or not plan.upstream_url:
                raise VerifiedSelectionError("Verified upstream URL unavailable")
            try:
                token, _ = reserve_live_channel(
                    redis_client, spec, channel_id=channel_id,
                    owner_lease=owner_lease,
                )
            except ReservationFull:
                at_capacity = True
                continue
            except ReservationBusy:
                # An existing alias needs token-bound attestation, not another
                # reservation or a stale assignment release.
                raise

            try:
                user_agent = account.get_user_agent_string()
                if not isinstance(user_agent, str):
                    raise VerifiedSelectionError("Selected user agent is unavailable")
                return VerifiedLiveSelection(
                    channel_id=channel_id, owner_lease=owner_lease,
                    spec=spec, token=token, stream_url=plan.upstream_url,
                    user_agent=user_agent,
                    transcode=False,
                    output_profile_id=output_profile.id,
                )
            except Exception:
                try:
                    released = release_pending_live_channel(
                        redis_client, spec, token, channel_id=channel_id,
                        owner_lease=owner_lease,
                    )
                except Exception:
                    raise VerifiedSelectionError(
                        "Pending reservation needs reconciliation"
                    ) from None
                if not released:
                    raise VerifiedSelectionError(
                        "Pending reservation changed during rollback"
                    ) from None
                raise VerifiedSelectionError(
                    "Verified URL resolution failed"
                ) from None

    if at_capacity:
        raise ReservationFull("Verified upstream capacity is full")
    raise VerifiedSelectionError("No eligible verified provider profile")
