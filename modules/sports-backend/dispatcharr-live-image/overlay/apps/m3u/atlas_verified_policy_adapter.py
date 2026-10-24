"""Default-off trusted policy adapter for a future verified live owner caller.

The constructor requires authoritative server-held dependencies. No production
call site installs this adapter and no request field can supply its realm/key.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from apps.m3u.verified_live_policy import (
    TrustedCapacityObservation,
    TrustedSourceBinding,
    VerifiedLivePolicyUnavailable,
    build_verified_live_spec,
)
from apps.m3u.strict_effective_credentials import verified_live_stream_url
from apps.m3u.verified_live_plan import VerifiedLivePlan


@dataclass(frozen=True, slots=True)
class ProviderCapacityEvidence:
    account_id: int
    status: str
    max_connections: int
    active_connections: int
    observed_at_unix: int


class AtlasVerifiedPolicyAdapter:
    """Build a reservation spec from two independent trusted authorities."""

    def __init__(self, *, claim_client,
                 capacity_reader, transformed_credentials, scope_key: bytes,
                 now_unix=None) -> None:
        self.claim_client = claim_client
        self.capacity_reader = capacity_reader
        self.transformed_credentials = transformed_credentials
        self.scope_key = scope_key
        self.now_unix = now_unix

    def __call__(self, channel, stream, profile, account, owner_lease):
        try:
            channel_uuid = str(channel.uuid)
            claims = self.claim_client.fetch(channel_uuid)
            matches = [claim for claim in claims if claim.account_id == account.id]
            if len(matches) != 1:
                raise VerifiedLivePolicyUnavailable("Account not authorized for event")
            claim = matches[0]
            if claim.channel_uuid != channel_uuid:
                raise VerifiedLivePolicyUnavailable("Atlas channel identity changed")
            realm = getattr(claim, "credential_realm", None)
            if not isinstance(realm, str) or not re.fullmatch(
                r"[a-z0-9][a-z0-9.-]{0,127}", realm
            ):
                raise VerifiedLivePolicyUnavailable("Canonical provider realm unavailable")
            credentials = self.transformed_credentials(account, profile)
            if (not isinstance(credentials, tuple) or len(credentials) != 3
                    or not all(isinstance(item, str) and item for item in credentials)):
                raise VerifiedLivePolicyUnavailable("Effective playback identity unavailable")
            evidence = self.capacity_reader(account, credentials)
            if (not isinstance(evidence, ProviderCapacityEvidence)
                    or evidence.account_id != account.id):
                raise VerifiedLivePolicyUnavailable("Provider observation unavailable")
            spec = build_verified_live_spec(
                channel_id=channel_uuid,
                owner_lease=owner_lease,
                stream=stream,
                profile=profile,
                account=account,
                binding=TrustedSourceBinding(
                    source_id=claim.source_id,
                    channel_id=channel_uuid,
                    account_id=claim.account_id,
                    profile_id=profile.id,
                    canonical_realm=realm,
                    configured_max_connections=claim.configured_max_connections,
                    enabled=True,
                ),
                observation=TrustedCapacityObservation(
                    account_id=evidence.account_id,
                    canonical_realm=realm,
                    status=evidence.status,
                    provider_max_connections=evidence.max_connections,
                    observed_at_unix=evidence.observed_at_unix,
                ),
                event_resource_source_ids=frozenset(
                    item.source_id for item in claims
                ),
                transformed_username=credentials[1],
                transformed_password=credentials[2],
                scope_key=self.scope_key,
                now_unix=self.now_unix,
            )
            return VerifiedLivePlan(
                spec=spec,
                upstream_url=verified_live_stream_url(stream, credentials),
            )
        except VerifiedLivePolicyUnavailable:
            raise
        except Exception:
            # HTTP, DB and provider exceptions can contain authenticated URLs.
            raise VerifiedLivePolicyUnavailable(
                "Verified live authority unavailable"
            ) from None

    def spec_for_selected(self, channel_uuid: str, stream_id: int,
                          profile_id: int, account_id: int, owner_lease: str):
        """Rebuild policy from ORM membership, never from Redis alias authority."""
        try:
            if (type(stream_id) is not int or type(profile_id) is not int
                or type(account_id) is not int
                or min(stream_id, profile_id, account_id) < 1):
                raise VerifiedLivePolicyUnavailable("Selected identity invalid")
            from apps.channels.models import Channel

            channel = Channel.objects.get(uuid=channel_uuid)
            stream = channel.streams.filter(id=stream_id).select_related(
                "m3u_account").get()
            account = stream.m3u_account
            if account is None or account.id != account_id:
                raise VerifiedLivePolicyUnavailable("Selected account changed")
            profile = account.profiles.get(id=profile_id, is_active=True)
            return self(channel, stream, profile, account, owner_lease).spec
        except VerifiedLivePolicyUnavailable:
            raise
        except Exception:
            raise VerifiedLivePolicyUnavailable(
                "Selected live policy unavailable"
            ) from None
