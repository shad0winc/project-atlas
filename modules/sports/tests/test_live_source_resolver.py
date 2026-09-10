from __future__ import annotations

import pytest

from live_source_resolver import (
    DispatcharrStreamCandidate,
    LiveSourceMatchKind,
    LiveSourceResolutionError,
    TeamRole,
    resolve_live_source_content,
)
from source_lifecycle import SportsSource


def _event() -> dict[str, object]:
    return {
        "provider": "thesportsdb",
        "provider_event_id": "2475374",
        "name": (
            "Seattle Seahawks vs "
            "New England Patriots"
        ),
        "sport": "American Football",
        "league": "NFL",
        "start_at": (
            "2026-09-10T00:20:00+00:00"
        ),
        "home_team": "Seattle Seahawks",
        "away_team": "New England Patriots",
    }


def _source(
    source_id: str,
    account_id: int,
    *,
    priority: int,
    enabled: bool = True,
    kind: str = "licensed_subscription",
) -> SportsSource:
    return SportsSource.from_mapping(
        {
            "source_id": source_id,
            "display_name": source_id,
            "provider_id": source_id,
            "provider_display_name": (
                source_id
            ),
            "account_display_name": (
                "Primary"
            ),
            "kind": kind,
            "enabled": enabled,
            "priority": priority,
            "max_connections": 3,
            "backend_reference": (
                f"dispatcharr:m3u:"
                f"{account_id}"
            ),
        }
    )


def _stream(
    stream_id: int,
    name: str,
    account_id: int,
    *,
    group: str = "AM | USA NFL",
    stale: bool = False,
) -> DispatcharrStreamCandidate:
    return DispatcharrStreamCandidate(
        stream_id=stream_id,
        name=name,
        m3u_account_id=account_id,
        group_name=group,
        is_stale=stale,
    )


def test_content_eligibility_precedes_source_priority() -> None:
    sources = (
        _source(
            "xc-4-account",
            4,
            priority=1,
        ),
        _source(
            "xc-account-2",
            3,
            priority=2,
        ),
        _source(
            "evestv-account-1",
            2,
            priority=100,
        ),
    )

    result = resolve_live_source_content(
        event=_event(),
        sources=sources,
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
            _stream(
                1753,
                "MLB SEATTLE MARINERS HD",
                4,
                group="|NA| USA MLB",
            ),
        ),
    )

    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.TEAM_FALLBACK
    )
    assert result.resource_source_ids == (
        "evestv-account-1",
    )


def test_same_license_kind_does_not_imply_content_entitlement() -> None:
    sources = (
        _source(
            "line",
            3,
            priority=10,
        ),
        _source(
            "xc4",
            4,
            priority=20,
        ),
        _source(
            "evestv",
            2,
            priority=30,
        ),
    )

    result = resolve_live_source_content(
        event=_event(),
        sources=sources,
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is not None
    assert result.resource_source_ids == (
        "evestv",
    )


def test_exact_event_match_wins_over_team_fallback_globally() -> None:
    sources = (
        _source(
            "exact",
            4,
            priority=200,
        ),
        _source(
            "fallback",
            2,
            priority=1,
        ),
    )

    result = resolve_live_source_content(
        event=_event(),
        sources=sources,
        streams=(
            _stream(
                900,
                (
                    "NFL Seattle Seahawks x "
                    "New England Patriots"
                ),
                4,
            ),
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.EXACT_EVENT
    )
    assert result.resource_source_ids == (
        "exact",
    )
    assert [
        item.stream_id
        for item
        in result.matches[0].streams
    ] == [900]


def test_team_fallback_preserves_home_and_away_roles() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is not None
    assert result.matches[0].streams[0].stream_id == 181
    assert (
        result.matches[0]
        .streams[0]
        .team_role
        is TeamRole.HOME
    )
    assert result.matches[0].streams[1].stream_id == 175
    assert (
        result.matches[0]
        .streams[1]
        .team_role
        is TeamRole.AWAY
    )


def test_team_fallback_requires_both_teams_on_same_source() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "home-only",
                2,
                priority=10,
            ),
            _source(
                "away-only",
                3,
                priority=20,
            ),
        ),
        streams=(
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                3,
            ),
        ),
    )

    assert result is None


def test_wrong_sport_seattle_content_does_not_create_eligibility() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "wrong-sport",
                4,
                priority=1,
            ),
        ),
        streams=(
            _stream(
                1753,
                "MLB SEATTLE MARINERS HD",
                4,
                group="|NA| USA MLB",
            ),
            _stream(
                1704,
                "MLB NEW ENGLAND TEST",
                4,
                group="|NA| USA MLB",
            ),
        ),
    )

    assert result is None


def test_stale_streams_do_not_create_content_eligibility() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
                stale=True,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is None


def test_disabled_exact_source_does_not_block_enabled_fallback() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "disabled-exact",
                4,
                priority=1,
                enabled=False,
            ),
            _source(
                "enabled-fallback",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                900,
                (
                    "NFL Seattle Seahawks vs "
                    "New England Patriots"
                ),
                4,
            ),
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.TEAM_FALLBACK
    )
    assert result.resource_source_ids == (
        "enabled-fallback",
    )


def test_ambiguous_team_feed_fails_closed_for_source() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "ambiguous",
                2,
                priority=1,
            ),
        ),
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                1175,
                "US| NFL: PATRIOTS BACKUP",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is None


def test_ambiguous_source_does_not_block_other_valid_source() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "ambiguous",
                2,
                priority=1,
            ),
            _source(
                "valid",
                3,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                1175,
                "US| NFL: PATRIOTS BACKUP",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
            _stream(
                275,
                "NFL PATRIOTS HD",
                3,
            ),
            _stream(
                281,
                "NFL SEAHAWKS HD",
                3,
            ),
        ),
    )

    assert result is not None
    assert result.resource_source_ids == (
        "valid",
    )


def test_existing_ranker_orders_only_content_qualified_sources() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "licensed-later",
                2,
                priority=200,
            ),
            _source(
                "licensed-first",
                3,
                priority=100,
            ),
            _source(
                "official",
                4,
                priority=1,
                kind="official_free",
            ),
        ),
        streams=(
            _stream(
                201,
                "NFL PATRIOTS HD",
                2,
            ),
            _stream(
                202,
                "NFL SEAHAWKS HD",
                2,
            ),
            _stream(
                301,
                "NFL PATRIOTS HD",
                3,
            ),
            _stream(
                302,
                "NFL SEAHAWKS HD",
                3,
            ),
            _stream(
                401,
                "NFL PATRIOTS HD",
                4,
            ),
            _stream(
                402,
                "NFL SEAHAWKS HD",
                4,
            ),
        ),
    )

    assert result is not None
    assert result.resource_source_ids == (
        "licensed-first",
        "licensed-later",
        "official",
    )


def test_duplicate_dispatcharr_account_reference_fails_closed() -> None:
    with pytest.raises(
        LiveSourceResolutionError,
        match="same Dispatcharr account",
    ):
        resolve_live_source_content(
            event=_event(),
            sources=(
                _source(
                    "one",
                    2,
                    priority=1,
                ),
                _source(
                    "two",
                    2,
                    priority=2,
                ),
            ),
            streams=(),
        )


def test_duplicate_stream_identity_is_rejected() -> None:
    with pytest.raises(
        LiveSourceResolutionError,
        match="stream_id values must be unique",
    ):
        resolve_live_source_content(
            event=_event(),
            sources=(
                _source(
                    "evestv",
                    2,
                    priority=100,
                ),
            ),
            streams=(
                _stream(
                    175,
                    "NFL PATRIOTS HD",
                    2,
                ),
                _stream(
                    175,
                    "NFL SEAHAWKS HD",
                    2,
                ),
            ),
        )


def test_result_contract_contains_no_backend_reference_or_url() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                175,
                "NFL PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "NFL SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is not None

    rendered = repr(
        result.to_mapping()
    ).casefold()

    assert "backend_reference" not in rendered
    assert "dispatcharr:m3u" not in rendered
    assert "password" not in rendered
    assert "username" not in rendered
    assert "token" not in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered


def test_legacy_numeric_dispatcharr_reference_remains_eligible() -> None:
    legacy = SportsSource.from_mapping(
        {
            "source_id": "evestv-account-1",
            "display_name": "EVESTV",
            "provider_id": "evestv",
            "provider_display_name": "EVESTV",
            "account_display_name": "EVESTV Account",
            "kind": "licensed_subscription",
            "enabled": True,
            "priority": 100,
            "max_connections": 1,
            "backend_reference": "2",
        }
    )

    result = resolve_live_source_content(
        event=_event(),
        sources=(legacy,),
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is not None
    assert result.resource_source_ids == (
        "evestv-account-1",
    )


def test_old_dated_event_slot_does_not_pollute_team_fallback() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                1175,
                (
                    "US| NFL LIVE 02 - "
                    "8/27 8pm Patriots at Browns"
                ),
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.TEAM_FALLBACK
    )

    streams = (
        result.matches[0].streams
    )

    assert [
        stream.stream_id
        for stream in streams
    ] == [
        181,
        175,
    ]


@pytest.mark.parametrize(
    "event_name",
    (
        "US| NFL LIVE 03 [EVENT ONLY]",
        (
            "NFL Rams x Chargers "
            "start:2026-08-27T22:00:00"
        ),
        "NFL Rams x Chargers 2026-08-27",
    ),
)
def test_event_slot_shapes_do_not_become_team_fallbacks(
    event_name: str,
) -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
            _stream(
                999,
                event_name,
                2,
            ),
        ),
    )

    # Normal persistent team feeds still qualify.
    assert result is not None
    assert result.resource_source_ids == (
        "evestv",
    )


def test_only_historical_event_slot_for_team_does_not_qualify_source() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
            _stream(
                175,
                (
                    "US| NFL LIVE 02 - "
                    "8/27 8pm Patriots at Browns"
                ),
                2,
            ),
        ),
    )

    assert result is None


def test_invalid_non_dispatcharr_reference_does_not_create_eligibility() -> None:
    source = SportsSource.from_mapping(
        {
            "source_id": "invalid",
            "display_name": "Invalid",
            "kind": "licensed_subscription",
            "enabled": True,
            "priority": 1,
            "max_connections": 1,
            "backend_reference": "not-an-account",
        }
    )

    result = resolve_live_source_content(
        event=_event(),
        sources=(source,),
        streams=(
            _stream(
                175,
                "US| NFL: PATRIOTS HD",
                2,
            ),
            _stream(
                181,
                "US| NFL: SEAHAWKS HD",
                2,
            ),
        ),
    )

    assert result is None


def test_exact_event_rejects_explicit_old_iso_date() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                900,
                (
                    "NFL Seattle Seahawks vs "
                    "New England Patriots "
                    "2026-08-27"
                ),
                2,
            ),
        ),
    )

    assert result is None


def test_exact_event_rejects_explicit_old_month_day() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                900,
                (
                    "NFL Seattle Seahawks vs "
                    "New England Patriots 8/27"
                ),
                2,
            ),
        ),
    )

    assert result is None


def test_exact_event_accepts_matching_iso_date() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                900,
                (
                    "NFL Seattle Seahawks vs "
                    "New England Patriots "
                    "2026-09-10"
                ),
                2,
            ),
        ),
    )

    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.EXACT_EVENT
    )


def test_exact_event_accepts_adjacent_local_calendar_date() -> None:
    event = _event()
    event["provider_event_id"] = "rams-49ers"
    event["name"] = (
        "San Francisco 49ers vs "
        "Los Angeles Rams"
    )
    event["home_team"] = (
        "San Francisco 49ers"
    )
    event["away_team"] = (
        "Los Angeles Rams"
    )
    event["start_at"] = (
        "2026-09-11T00:35:00+00:00"
    )

    result = resolve_live_source_content(
        event=event,
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                900,
                (
                    "NFL San Francisco 49ers vs "
                    "Los Angeles Rams 9/10"
                ),
                2,
            ),
        ),
    )

    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.EXACT_EVENT
    )


def test_exact_event_without_temporal_evidence_remains_valid() -> None:
    result = resolve_live_source_content(
        event=_event(),
        sources=(
            _source(
                "evestv",
                2,
                priority=100,
            ),
        ),
        streams=(
            _stream(
                900,
                (
                    "NFL Seattle Seahawks vs "
                    "New England Patriots"
                ),
                2,
            ),
        ),
    )

    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.EXACT_EVENT
    )


def test_event_requires_timezone_aware_start_at() -> None:
    event = _event()
    event["start_at"] = (
        "2026-09-10T00:20:00"
    )

    with pytest.raises(
        LiveSourceResolutionError,
        match="start_at must include a timezone",
    ):
        resolve_live_source_content(
            event=event,
            sources=(),
            streams=(),
        )


def test_event_rejects_invalid_start_at() -> None:
    event = _event()
    event["start_at"] = "not-a-time"

    with pytest.raises(
        LiveSourceResolutionError,
        match="start_at must be an ISO-8601 timestamp",
    ):
        resolve_live_source_content(
            event=event,
            sources=(),
            streams=(),
        )
