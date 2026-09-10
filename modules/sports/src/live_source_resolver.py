from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Iterable

from source_lifecycle import (
    SourceCandidate,
    SportsSource,
    rank_source_candidates,
)


class LiveSourceResolutionError(ValueError):
    """Raised when event/source resolution input violates its contract."""


class LiveSourceMatchKind(StrEnum):
    EXACT_EVENT = "exact_event"
    TEAM_FALLBACK = "team_fallback"


class TeamRole(StrEnum):
    HOME = "home"
    AWAY = "away"


@dataclass(frozen=True, slots=True)
class DispatcharrStreamCandidate:
    """Secret-free Dispatcharr stream identity used for resolution."""

    stream_id: int
    name: str
    m3u_account_id: int
    group_name: str | None = None
    is_stale: bool = False

    def __post_init__(self) -> None:
        if (
            isinstance(self.stream_id, bool)
            or not isinstance(self.stream_id, int)
            or self.stream_id < 1
        ):
            raise LiveSourceResolutionError(
                "stream_id must be a positive integer"
            )

        name = str(self.name or "").strip()

        if not name:
            raise LiveSourceResolutionError(
                "stream name is required"
            )

        if (
            isinstance(self.m3u_account_id, bool)
            or not isinstance(self.m3u_account_id, int)
            or self.m3u_account_id < 1
        ):
            raise LiveSourceResolutionError(
                "m3u_account_id must be a positive integer"
            )

        group_name = self.group_name

        if group_name is not None:
            group_name = str(group_name).strip() or None

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "group_name",
            group_name,
        )


@dataclass(frozen=True, slots=True)
class ResolvedStream:
    stream_id: int
    name: str
    team_role: TeamRole | None = None

    def to_mapping(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "stream_id": self.stream_id,
            "name": self.name,
        }

        if self.team_role is not None:
            payload["team_role"] = self.team_role.value

        return payload


@dataclass(frozen=True, slots=True)
class ResolvedSourceMatch:
    """One content-qualified Atlas Sports source."""

    source_id: str
    kind: LiveSourceMatchKind
    streams: tuple[ResolvedStream, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind.value,
            "streams": [
                stream.to_mapping()
                for stream in self.streams
            ],
        }


@dataclass(frozen=True, slots=True)
class LiveSourceResolution:
    provider: str
    provider_event_id: str
    match_kind: LiveSourceMatchKind
    matches: tuple[ResolvedSourceMatch, ...]
    ranked_sources: tuple[SourceCandidate, ...]

    @property
    def resource_source_ids(self) -> tuple[str, ...]:
        return tuple(
            candidate.source_id
            for candidate in self.ranked_sources
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_event_id": self.provider_event_id,
            "match_kind": self.match_kind.value,
            "resource_source_ids": list(
                self.resource_source_ids
            ),
            "matches": [
                match.to_mapping()
                for match in self.matches
            ],
        }


@dataclass(frozen=True, slots=True)
class _EventIdentity:
    provider: str
    provider_event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    start_at: datetime


def _required_text(
    value: object,
    field: str,
) -> str:
    text = str(value or "").strip()

    if not text:
        raise LiveSourceResolutionError(
            f"{field} is required"
        )

    return text


def _event_start_at(
    value: object,
) -> datetime:
    text = _required_text(
        value,
        "start_at",
    )

    candidate = (
        text[:-1] + "+00:00"
        if text.endswith("Z")
        else text
    )

    try:
        parsed = datetime.fromisoformat(
            candidate
        )
    except ValueError as error:
        raise LiveSourceResolutionError(
            "start_at must be an ISO-8601 timestamp"
        ) from error

    if parsed.tzinfo is None:
        raise LiveSourceResolutionError(
            "start_at must include a timezone"
        )

    return parsed.astimezone(
        timezone.utc
    )


def _event_identity(
    event: dict[str, Any],
) -> _EventIdentity:
    if not isinstance(event, dict):
        raise LiveSourceResolutionError(
            "event must be an object"
        )

    return _EventIdentity(
        provider=_required_text(
            event.get("provider"),
            "provider",
        ).lower(),
        provider_event_id=_required_text(
            event.get("provider_event_id"),
            "provider_event_id",
        ),
        sport=_required_text(
            event.get("sport"),
            "sport",
        ),
        league=_required_text(
            event.get("league"),
            "league",
        ),
        home_team=_required_text(
            event.get("home_team"),
            "home_team",
        ),
        away_team=_required_text(
            event.get("away_team"),
            "away_team",
        ),
        start_at=_event_start_at(
            event.get("start_at")
        ),
    )


def _normalize_words(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in re.sub(
            r"[^a-z0-9]+",
            " ",
            value.casefold(),
        ).split()
        if token
    )


def _normalized_phrase(value: str) -> str:
    return " ".join(
        _normalize_words(value)
    )


def _team_aliases(team_name: str) -> tuple[str, ...]:
    words = _normalize_words(team_name)

    if not words:
        return ()

    full_name = " ".join(words)
    nickname = words[-1]

    aliases = [full_name]

    if nickname != full_name:
        aliases.append(nickname)

    # Preserve order while removing duplicates.
    return tuple(dict.fromkeys(aliases))


def _contains_phrase(
    normalized_text: str,
    phrase: str,
) -> bool:
    return (
        f" {phrase} "
        in f" {normalized_text} "
    )


def _matches_team(
    normalized_name: str,
    team_name: str,
) -> bool:
    return any(
        _contains_phrase(
            normalized_name,
            alias,
        )
        for alias in _team_aliases(
            team_name
        )
    )


def _league_aliases(
    *,
    sport: str,
    league: str,
) -> tuple[str, ...]:
    league_words = _normalize_words(league)
    sport_words = _normalize_words(sport)

    aliases: list[str] = []

    if league_words:
        aliases.append(
            " ".join(league_words)
        )

    compact_league = "".join(
        league_words
    )

    if compact_league:
        aliases.append(
            compact_league
        )

    if sport_words:
        aliases.append(
            " ".join(sport_words)
        )

    return tuple(
        dict.fromkeys(aliases)
    )


def _is_league_scoped(
    stream: DispatcharrStreamCandidate,
    event: _EventIdentity,
) -> bool:
    combined = _normalized_phrase(
        " ".join(
            part
            for part in (
                stream.group_name,
                stream.name,
            )
            if part
        )
    )

    return any(
        _contains_phrase(
            combined,
            alias,
        )
        for alias in _league_aliases(
            sport=event.sport,
            league=event.league,
        )
    )


def _dispatcharr_account_id(
    source: SportsSource,
) -> int | None:
    """Return the Dispatcharr M3U account behind one Sports source.

    New provider-account records use the opaque canonical form
    ``dispatcharr:m3u:N``.

    Legacy v1 Sports source records may contain the original bare
    positive integer reference. Those records remain valid for
    playback/content resolution, but new writes continue to use the
    canonical form.
    """

    reference = str(
        source.backend_reference or ""
    ).strip()

    prefix = "dispatcharr:m3u:"

    if reference.startswith(prefix):
        raw_id = reference[
            len(prefix):
        ]
    else:
        raw_id = reference

    if (
        not raw_id.isdigit()
        or int(raw_id) < 1
    ):
        return None

    return int(raw_id)


def _eligible_source_accounts(
    sources: Iterable[SportsSource],
) -> dict[int, SportsSource]:
    accounts: dict[int, SportsSource] = {}

    for source in sources:
        if not source.enabled:
            continue

        account_id = _dispatcharr_account_id(
            source
        )

        if account_id is None:
            continue

        if account_id in accounts:
            raise LiveSourceResolutionError(
                "multiple enabled Sports sources "
                "reference the same Dispatcharr account"
            )

        accounts[account_id] = source

    return accounts


def _candidate_streams(
    *,
    event: _EventIdentity,
    streams: Iterable[
        DispatcharrStreamCandidate
    ],
    sources_by_account: dict[
        int,
        SportsSource,
    ],
) -> dict[str, list[
    DispatcharrStreamCandidate
]]:
    by_source: dict[
        str,
        list[DispatcharrStreamCandidate],
    ] = {}

    seen_stream_ids: set[int] = set()

    for stream in streams:
        if stream.stream_id in seen_stream_ids:
            raise LiveSourceResolutionError(
                "stream_id values must be unique"
            )

        seen_stream_ids.add(
            stream.stream_id
        )

        if stream.is_stale:
            continue

        source = sources_by_account.get(
            stream.m3u_account_id
        )

        if source is None:
            continue

        if not _is_league_scoped(
            stream,
            event,
        ):
            continue

        by_source.setdefault(
            source.source_id,
            [],
        ).append(stream)

    return by_source


def _compatible_event_dates(
    event: _EventIdentity,
) -> frozenset[date]:
    event_date = event.start_at.date()

    return frozenset(
        {
            event_date - timedelta(days=1),
            event_date,
            event_date + timedelta(days=1),
        }
    )


def _stream_temporal_dates(
    stream: DispatcharrStreamCandidate,
    *,
    event: _EventIdentity,
) -> tuple[date, ...]:
    """Extract explicit calendar-date evidence from a stream name.

    Dispatcharr/provider stream labels are not guaranteed to identify
    their timezone. Compare calendar dates only and tolerate the
    adjacent UTC dates so local provider labels do not become false
    contradictions.
    """

    name = stream.name

    dates: list[date] = []

    for match in re.finditer(
        r"\b(20\d{2})-(\d{2})-(\d{2})\b",
        name,
    ):
        try:
            parsed = date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
        except ValueError:
            continue

        dates.append(parsed)

    # M/D labels such as "9/10" do not carry a year.
    # Interpret them against the event year and the immediately
    # adjacent years so year boundaries remain deterministic.
    for match in re.finditer(
        r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)",
        name,
    ):
        month = int(match.group(1))
        day = int(match.group(2))

        for year in (
            event.start_at.year - 1,
            event.start_at.year,
            event.start_at.year + 1,
        ):
            try:
                parsed = date(
                    year,
                    month,
                    day,
                )
            except ValueError:
                continue

            if parsed in _compatible_event_dates(
                event
            ):
                dates.append(parsed)
                break
        else:
            # Preserve contradictory M/D evidence with the event
            # year so the caller can reject it.
            try:
                dates.append(
                    date(
                        event.start_at.year,
                        month,
                        day,
                    )
                )
            except ValueError:
                pass

    return tuple(
        dict.fromkeys(dates)
    )


def _temporal_evidence_compatible(
    stream: DispatcharrStreamCandidate,
    *,
    event: _EventIdentity,
) -> bool:
    temporal_dates = _stream_temporal_dates(
        stream,
        event=event,
    )

    # No explicit date evidence is not itself a contradiction.
    if not temporal_dates:
        return True

    compatible = _compatible_event_dates(
        event
    )

    return all(
        candidate in compatible
        for candidate in temporal_dates
    )


def _exact_matches(
    *,
    event: _EventIdentity,
    streams_by_source: dict[
        str,
        list[DispatcharrStreamCandidate],
    ],
) -> dict[str, ResolvedSourceMatch]:
    matches: dict[
        str,
        ResolvedSourceMatch,
    ] = {}

    for source_id, streams in (
        streams_by_source.items()
    ):
        exact = []

        for stream in streams:
            normalized = (
                _normalized_phrase(
                    stream.name
                )
            )

            if (
                _matches_team(
                    normalized,
                    event.home_team,
                )
                and _matches_team(
                    normalized,
                    event.away_team,
                )
                and _temporal_evidence_compatible(
                    stream,
                    event=event,
                )
            ):
                exact.append(stream)

        # More than one exact stream for one
        # source is ambiguous in this first
        # resolver contract. Fail closed for
        # that source.
        if len(exact) != 1:
            continue

        stream = exact[0]

        matches[source_id] = (
            ResolvedSourceMatch(
                source_id=source_id,
                kind=(
                    LiveSourceMatchKind
                    .EXACT_EVENT
                ),
                streams=(
                    ResolvedStream(
                        stream_id=(
                            stream.stream_id
                        ),
                        name=stream.name,
                    ),
                ),
            )
        )

    return matches


def _looks_event_specific(
    stream: DispatcharrStreamCandidate,
) -> bool:
    """Identify rotating/dated event slots that must not be team fallbacks.

    Persistent team channels are valid fallback material. Historical or
    rotating event slots are not: merely mentioning one participant in
    another event must not make a source ambiguous or eligible.
    """

    name = stream.name.casefold()

    return bool(
        re.search(
            r"\b\d{1,2}/\d{1,2}\b",
            name,
        )
        or re.search(
            r"\b20\d{2}-\d{2}-\d{2}\b",
            name,
        )
        or "start:" in name
        or "stop:" in name
        or "event only" in name
        or re.search(
            r"\bnfl\s+live\s+\d+\b",
            name,
        )
    )


def _team_fallback_matches(
    *,
    event: _EventIdentity,
    streams_by_source: dict[
        str,
        list[DispatcharrStreamCandidate],
    ],
) -> dict[str, ResolvedSourceMatch]:
    matches: dict[
        str,
        ResolvedSourceMatch,
    ] = {}

    for source_id, streams in (
        streams_by_source.items()
    ):
        home: list[
            DispatcharrStreamCandidate
        ] = []
        away: list[
            DispatcharrStreamCandidate
        ] = []

        for stream in streams:
            if _looks_event_specific(
                stream
            ):
                continue

            normalized = (
                _normalized_phrase(
                    stream.name
                )
            )

            home_match = _matches_team(
                normalized,
                event.home_team,
            )
            away_match = _matches_team(
                normalized,
                event.away_team,
            )

            # A fallback stream must identify
            # exactly one side. A stream naming
            # both sides belongs to the exact
            # event class instead.
            if home_match and not away_match:
                home.append(stream)
            elif away_match and not home_match:
                away.append(stream)

        # The v1 fallback requires one
        # unambiguous stream for each team.
        if (
            len(home) != 1
            or len(away) != 1
        ):
            continue

        matches[source_id] = (
            ResolvedSourceMatch(
                source_id=source_id,
                kind=(
                    LiveSourceMatchKind
                    .TEAM_FALLBACK
                ),
                streams=(
                    ResolvedStream(
                        stream_id=(
                            home[0].stream_id
                        ),
                        name=home[0].name,
                        team_role=TeamRole.HOME,
                    ),
                    ResolvedStream(
                        stream_id=(
                            away[0].stream_id
                        ),
                        name=away[0].name,
                        team_role=TeamRole.AWAY,
                    ),
                ),
            )
        )

    return matches


def _rank_matches(
    *,
    matches: dict[
        str,
        ResolvedSourceMatch,
    ],
    sources: Iterable[SportsSource],
) -> tuple[
    tuple[ResolvedSourceMatch, ...],
    tuple[SourceCandidate, ...],
]:
    source_by_id = {
        source.source_id: source
        for source in sources
    }

    qualified_sources = [
        source_by_id[source_id]
        for source_id in matches
        if source_id in source_by_id
    ]

    ranked = rank_source_candidates(
        qualified_sources
    )

    ordered_matches = tuple(
        matches[candidate.source_id]
        for candidate in ranked
    )

    return (
        ordered_matches,
        ranked,
    )


def resolve_live_source_content(
    *,
    event: dict[str, Any],
    streams: Iterable[
        DispatcharrStreamCandidate
    ],
    sources: Iterable[SportsSource],
) -> LiveSourceResolution | None:
    """Resolve content before applying Atlas source ranking.

    Resolution is intentionally pure and secret-free.

    Policy:
    1. Only enabled Sports sources with a valid Dispatcharr
       M3U account reference can become eligible.
    2. Only non-stale streams scoped to the event's sport /
       league participate.
    3. Exact streams naming both teams are preferred globally.
    4. If no exact source is available, one unambiguous
       home-team and away-team stream on the same source
       qualifies that source for team fallback.
    5. Only content-qualified sources are passed to the
       existing Atlas source ranker.
    6. Ambiguity fails closed by excluding that source.
    """

    identity = _event_identity(
        event
    )

    source_tuple = tuple(
        sources
    )
    stream_tuple = tuple(
        streams
    )

    source_ids = [
        source.source_id
        for source in source_tuple
    ]

    if len(source_ids) != len(
        set(source_ids)
    ):
        raise LiveSourceResolutionError(
            "source_id values must be unique"
        )

    sources_by_account = (
        _eligible_source_accounts(
            source_tuple
        )
    )

    streams_by_source = (
        _candidate_streams(
            event=identity,
            streams=stream_tuple,
            sources_by_account=(
                sources_by_account
            ),
        )
    )

    matches = _exact_matches(
        event=identity,
        streams_by_source=(
            streams_by_source
        ),
    )

    if matches:
        match_kind = (
            LiveSourceMatchKind
            .EXACT_EVENT
        )
    else:
        matches = _team_fallback_matches(
            event=identity,
            streams_by_source=(
                streams_by_source
            ),
        )

        if not matches:
            return None

        match_kind = (
            LiveSourceMatchKind
            .TEAM_FALLBACK
        )

    ordered_matches, ranked = (
        _rank_matches(
            matches=matches,
            sources=source_tuple,
        )
    )

    if not ranked:
        return None

    return LiveSourceResolution(
        provider=identity.provider,
        provider_event_id=(
            identity.provider_event_id
        ),
        match_kind=match_kind,
        matches=ordered_matches,
        ranked_sources=ranked,
    )
