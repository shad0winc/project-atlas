from __future__ import annotations

from collections.abc import Iterable

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
