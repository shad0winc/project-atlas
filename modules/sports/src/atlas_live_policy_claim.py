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
    provider: str | None
    provider_event_id: str | None
    identity_kind: str = "event"
    standalone_channel_id: str | None = None
    stream_id: int | None = None

    def to_mapping(self) -> dict[str, object]:
        if self.identity_kind == "standalone":
            return {
                "channel_uuid": self.channel_uuid, "source_id": self.source_id,
                "account_id": self.account_id,
                "configured_max_connections": self.configured_max_connections,
                "credential_realm": self.credential_realm,
                "identity_kind": "standalone",
                "standalone_channel_id": self.standalone_channel_id,
                **({"stream_id": self.stream_id} if self.stream_id is not None else {}),
            }
        return {
            "channel_uuid": self.channel_uuid,
            "source_id": self.source_id,
            "account_id": self.account_id,
            "configured_max_connections": self.configured_max_connections,
            "credential_realm": self.credential_realm,
            "provider": self.provider,
            "provider_event_id": self.provider_event_id,
            **({"stream_id": self.stream_id} if self.stream_id is not None else {}),
        }


def _published_route(channel_uuid, channel_bindings, live_sources):
    bindings = [row for row in channel_bindings if row.dispatcharr_channel_uuid == channel_uuid]
    if len(bindings) != 1:
        raise AtlasLivePolicyUnavailable("Channel binding unavailable or ambiguous")
    binding = bindings[0]
    routes = []
    for live in live_sources:
        options = getattr(live, "playback_options", ())
        if options:
            for option in options:
                if option.channel_id(live.atlas_channel_id) == binding.atlas_channel_id:
                    routes.append((live, option))
        elif live.atlas_channel_id == binding.atlas_channel_id:
            routes.append((live, None))
    if len(routes) != 1:
        raise AtlasLivePolicyUnavailable("Published source unavailable or ambiguous")
    live, option = routes[0]
    if option is None:
        return live, live.stream_url, live.resource_source_ids, None
    if (option.dispatcharr_channel_uuid != channel_uuid
            or option.dispatcharr_channel_id != binding.dispatcharr_channel_id
            or type(option.dispatcharr_stream_id) is not int
            or option.dispatcharr_stream_id <= 0
            or option.resource_source_id not in live.resource_source_ids):
        raise AtlasLivePolicyUnavailable("Playback option identity changed")
    return live, option.stream_url, (option.resource_source_id,), option.dispatcharr_stream_id


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

    live, stream_url, resources, stream_id = _published_route(
        channel_uuid, channel_bindings, live_sources,
    )
    if source_id not in resources or len(set(resources)) != len(resources):
        raise AtlasLivePolicyUnavailable("Event source membership changed")
    parsed = urlsplit(stream_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or
            not parsed.path.endswith("/proxy/ts/stream/" + channel_uuid)
            or unquote(parsed.path.rsplit("/", 1)[-1]) != channel_uuid):
        raise AtlasLivePolicyUnavailable("Published channel URL changed")
    standalone = getattr(live, "standalone", False)
    if type(standalone) is not bool:
        raise AtlasLivePolicyUnavailable("Live identity kind invalid")
    if standalone:
        if (live.provider is not None or live.provider_event_id is not None
                or not re.fullmatch(r"sports-live-[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", live.atlas_channel_id)):
            raise AtlasLivePolicyUnavailable("Standalone channel identity unavailable")
    elif (not isinstance(live.provider, str) or not live.provider
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
        "standalone" if standalone else "event",
        live.atlas_channel_id if standalone else None, stream_id,
    )


def claims_for_channel(*, channel_uuid: str, lifecycle_sources,
                       channel_bindings, live_sources) -> tuple[AtlasLivePolicyClaim, ...]:
    """Return all distinct account authorities for a published channel."""
    bindings = tuple(channel_bindings)
    live_rows = tuple(live_sources)
    sources = tuple(lifecycle_sources)
    _, _, resources, _ = _published_route(channel_uuid, bindings, live_rows)
    if not resources:
        raise AtlasLivePolicyUnavailable("Published source has no authorized accounts")
    claims = tuple(claim_for_channel(
        channel_uuid=channel_uuid, source_id=source_id,
        lifecycle_sources=sources, channel_bindings=bindings, live_sources=live_rows,
    ) for source_id in resources)
    if len({claim.account_id for claim in claims}) != len(claims):
        raise AtlasLivePolicyUnavailable("Multiple event sources share an account")
    return claims
