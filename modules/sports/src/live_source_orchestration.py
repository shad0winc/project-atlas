from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from dispatcharr_admin import (
    DispatcharrAdminClient,
    SafeDispatcharrStream,
)
from live_source_resolver import (
    DispatcharrStreamCandidate,
    LiveSourceResolution,
    resolve_live_source_content,
)
from source_lifecycle import SportsSource


_DISPATCHARR_M3U_PREFIX = "dispatcharr:m3u:"


@dataclass(frozen=True, slots=True)
class ProvisioningSourceStreams:
    """Resolved Dispatcharr stream identities for one ranked Sports source."""

    source_id: str
    stream_ids: tuple[int, ...]

    def to_mapping(
        self,
    ) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "stream_ids": list(
                self.stream_ids
            ),
        }


@dataclass(frozen=True, slots=True)
class LiveSourceProvisioningPlan:
    """Pure desired-state description for one shared Sports live event."""

    source_id: str
    atlas_channel_id: str
    name: str
    provider: str
    provider_event_id: str
    match_kind: str
    resource_source_ids: tuple[str, ...]
    source_streams: tuple[
        ProvisioningSourceStreams,
        ...
    ]

    @property
    def stream_ids(
        self,
    ) -> tuple[int, ...]:
        return tuple(
            stream_id
            for source
            in self.source_streams
            for stream_id
            in source.stream_ids
        )

    def to_mapping(
        self,
    ) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "atlas_channel_id": (
                self.atlas_channel_id
            ),
            "name": self.name,
            "provider": self.provider,
            "provider_event_id": (
                self.provider_event_id
            ),
            "match_kind": self.match_kind,
            "resource_source_ids": list(
                self.resource_source_ids
            ),
            "source_streams": [
                source.to_mapping()
                for source
                in self.source_streams
            ],
            "stream_ids": list(
                self.stream_ids
            ),
        }


def _dispatcharr_account_id(
    source: SportsSource,
) -> int | None:
    """Return one valid Dispatcharr M3U account identity.

    The resolver remains authoritative for final eligibility. This helper
    exists only so orchestration can avoid making discovery requests for
    disabled or unrelated Sports sources.
    """

    if not source.enabled:
        return None

    reference = str(
        source.backend_reference or ""
    ).strip()

    if reference.startswith(
        _DISPATCHARR_M3U_PREFIX
    ):
        raw_id = reference[
            len(_DISPATCHARR_M3U_PREFIX):
        ]
    else:
        # Legacy v1 Sports source records may contain the original
        # bare positive integer Dispatcharr account reference.
        # Resolver compatibility requires those accounts to remain
        # discoverable; new writes continue to use the canonical form.
        raw_id = reference

    if (
        not raw_id.isdigit()
        or int(raw_id) < 1
    ):
        return None

    return int(raw_id)


def _eligible_account_ids(
    sources: Iterable[SportsSource],
) -> tuple[int, ...]:
    """Return unique eligible backend accounts in deterministic order."""

    account_ids: list[int] = []
    seen: set[int] = set()

    for source in sources:
        account_id = _dispatcharr_account_id(
            source
        )

        if (
            account_id is None
            or account_id in seen
        ):
            continue

        seen.add(account_id)
        account_ids.append(account_id)

    return tuple(account_ids)


def _resolver_candidate(
    stream: SafeDispatcharrStream,
) -> DispatcharrStreamCandidate:
    """Translate the secret-free Dispatcharr DTO into resolver input."""

    return DispatcharrStreamCandidate(
        stream_id=stream.stream_id,
        name=stream.name,
        m3u_account_id=(
            stream.m3u_account_id
        ),
        group_name=stream.group_name,
        is_stale=stream.is_stale,
    )


def resolve_event_live_source_content(
    *,
    event: dict[str, object],
    sources: Iterable[SportsSource],
    dispatcharr: DispatcharrAdminClient,
) -> LiveSourceResolution | None:
    """Resolve authorized Sports content from imported Dispatcharr streams.

    This boundary is intentionally read-only:

    * eligible backend accounts are discovered from enabled SportsSource
      records;
    * each unique eligible Dispatcharr account is queried exactly once;
    * only secret-free imported stream metadata crosses into the pure
      content resolver;
    * an authoritative empty stream result may resolve to None;
    * Dispatcharr/provider failures are not converted into empty state.

    Channel creation, LiveSource persistence, worker scheduling and runtime
    mutation belong to later orchestration layers.
    """

    source_tuple = tuple(sources)

    streams: list[
        DispatcharrStreamCandidate
    ] = []

    for account_id in _eligible_account_ids(
        source_tuple
    ):
        streams.extend(
            _resolver_candidate(stream)
            for stream in (
                dispatcharr.list_streams(
                    account_id=account_id
                )
            )
        )

    return resolve_live_source_content(
        event=event,
        streams=streams,
        sources=source_tuple,
    )



def build_live_source_provisioning_plan(
    *,
    event: dict[str, object],
    resolution: LiveSourceResolution,
) -> LiveSourceProvisioningPlan:
    """Build deterministic shared-channel desired state without mutation."""

    provider = str(
        event.get("provider") or ""
    ).strip().lower()

    provider_event_id = str(
        event.get("provider_event_id")
        or ""
    ).strip()

    name = str(
        event.get("name") or ""
    ).strip()

    if (
        not provider
        or not provider_event_id
        or not name
    ):
        raise ValueError(
            "provider, provider_event_id, "
            "and name are required"
        )

    if (
        resolution.provider != provider
        or resolution.provider_event_id
        != provider_event_id
    ):
        raise ValueError(
            "resolution event identity "
            "does not match event"
        )

    source_id = (
        f"{provider}-{provider_event_id}"
    )

    resource_source_ids = (
        resolution.resource_source_ids
    )

    matches_by_source = {
        match.source_id: match
        for match
        in resolution.matches
    }

    source_streams: list[
        ProvisioningSourceStreams
    ] = []

    for source_id_value in (
        resource_source_ids
    ):
        match = matches_by_source.get(
            source_id_value
        )

        if match is None:
            raise ValueError(
                "resolution resource source "
                "has no resolved stream match"
            )

        stream_ids = tuple(
            stream.stream_id
            for stream
            in match.streams
        )

        if not stream_ids:
            raise ValueError(
                "resolved source has no streams"
            )

        source_streams.append(
            ProvisioningSourceStreams(
                source_id=source_id_value,
                stream_ids=stream_ids,
            )
        )

    if not source_streams:
        raise ValueError(
            "resolution has no provisionable sources"
        )

    return LiveSourceProvisioningPlan(
        source_id=source_id,
        atlas_channel_id=(
            f"sports-live-{source_id}"
        ),
        name=name,
        provider=provider,
        provider_event_id=(
            provider_event_id
        ),
        match_kind=(
            resolution.match_kind.value
        ),
        resource_source_ids=(
            resource_source_ids
        ),
        source_streams=tuple(
            source_streams
        ),
    )
