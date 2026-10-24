"""Secret-free Atlas Sports authority claim for one Dispatcharr channel.

Call only behind a dedicated read-only private API credential. The claim is
not a provider capacity observation and cannot authorize playback by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import unquote, urlsplit
from uuid import UUID


class AtlasLivePolicyUnavailable(RuntimeError):
    """Atlas state cannot safely attest the requested source and channel."""


@dataclass(frozen=True, slots=True)
class AtlasLivePolicyClaim:
    channel_uuid: str
    source_id: str
    account_id: int
    configured_max_connections: int
    credential_realm: str
    provider: str
    provider_event_id: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "channel_uuid": self.channel_uuid,
            "source_id": self.source_id,
            "account_id": self.account_id,
            "configured_max_connections": self.configured_max_connections,
            "credential_realm": self.credential_realm,
            "provider": self.provider,
            "provider_event_id": self.provider_event_id,
        }


def claim_for_channel(*, channel_uuid: str, source_id: str,
                      lifecycle_sources, channel_bindings, live_sources) -> AtlasLivePolicyClaim:
    """Rebuild an exact claim from current Atlas registries, refusing drift."""
    try:
        if str(UUID(channel_uuid)) != channel_uuid:
            raise ValueError("noncanonical")
    except (TypeError, ValueError, AttributeError):
        raise AtlasLivePolicyUnavailable("Invalid channel identity") from None
    if not isinstance(source_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", source_id
    ):
        raise AtlasLivePolicyUnavailable("Invalid source identity")

    binding_rows = [
        row for row in channel_bindings
        if row.dispatcharr_channel_uuid == channel_uuid
    ]
    if len(binding_rows) != 1:
        raise AtlasLivePolicyUnavailable("Channel binding unavailable or ambiguous")
    binding = binding_rows[0]
    matching_live = [
        row for row in live_sources
        if row.atlas_channel_id == binding.atlas_channel_id
    ]
    if len(matching_live) != 1:
        raise AtlasLivePolicyUnavailable("Published source unavailable or ambiguous")
    live = matching_live[0]
    if source_id not in live.resource_source_ids or len(set(live.resource_source_ids)) != len(live.resource_source_ids):
        raise AtlasLivePolicyUnavailable("Event source membership changed")
    parsed = urlsplit(live.stream_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or
            not parsed.path.endswith("/proxy/ts/stream/" + channel_uuid)
            or unquote(parsed.path.rsplit("/", 1)[-1]) != channel_uuid):
        raise AtlasLivePolicyUnavailable("Published channel URL changed")
    if (not isinstance(live.provider, str) or not live.provider
            or not isinstance(live.provider_event_id, str) or not live.provider_event_id):
        raise AtlasLivePolicyUnavailable("Event identity unavailable")

    source_rows = [row for row in lifecycle_sources if row.source_id == source_id]
    if len(source_rows) != 1 or source_rows[0].enabled is not True:
        raise AtlasLivePolicyUnavailable("Source disabled or ambiguous")
    source = source_rows[0]
    realm = getattr(source, "credential_realm", None)
    if not isinstance(realm, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9.-]{0,127}", realm
    ):
        raise AtlasLivePolicyUnavailable("Credential realm not onboarded")
    reference = str(source.backend_reference or "")
    match = re.fullmatch(r"(?:dispatcharr:m3u:)?([1-9][0-9]*)", reference)
    if not match or type(source.max_connections) is not int or source.max_connections <= 0:
        raise AtlasLivePolicyUnavailable("Bounded Dispatcharr account unavailable")
    account_id = int(match.group(1))
    duplicates = [
        row for row in lifecycle_sources
        if row.enabled is True and row.source_id != source_id
        and str(row.backend_reference or "") in
            {str(account_id), f"dispatcharr:m3u:{account_id}"}
    ]
    if duplicates:
        raise AtlasLivePolicyUnavailable("Multiple enabled sources share an account")
    return AtlasLivePolicyClaim(
        channel_uuid, source_id, account_id, source.max_connections, realm,
        live.provider, live.provider_event_id,
    )


def claims_for_channel(*, channel_uuid: str, lifecycle_sources,
                       channel_bindings, live_sources) -> tuple[AtlasLivePolicyClaim, ...]:
    """Return all distinct account authorities for a published channel."""
    bindings = tuple(channel_bindings)
    live_rows = tuple(live_sources)
    sources = tuple(lifecycle_sources)
    matching = [row for row in bindings if row.dispatcharr_channel_uuid == channel_uuid]
    if len(matching) != 1:
        raise AtlasLivePolicyUnavailable("Channel binding unavailable or ambiguous")
    published = [row for row in live_rows if row.atlas_channel_id == matching[0].atlas_channel_id]
    if len(published) != 1 or not published[0].resource_source_ids:
        raise AtlasLivePolicyUnavailable("Published source unavailable or ambiguous")
    claims = tuple(claim_for_channel(
        channel_uuid=channel_uuid, source_id=source_id,
        lifecycle_sources=sources, channel_bindings=bindings, live_sources=live_rows,
    ) for source_id in published[0].resource_source_ids)
    if len({claim.account_id for claim in claims}) != len(claims):
        raise AtlasLivePolicyUnavailable("Multiple event sources share an account")
    return claims
