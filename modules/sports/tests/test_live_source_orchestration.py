from __future__ import annotations

import pytest

from dispatcharr_admin import (
    DispatcharrAdminError,
    SafeDispatcharrStream,
)
from live_source_orchestration import (
    build_live_source_provisioning_plan,
    resolve_event_live_source_content,
)
from live_source_resolver import (
    LiveSourceMatchKind,
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
        "away_team": (
            "New England Patriots"
        ),
    }


def _source(
    source_id: str,
    account_id: int,
    *,
    enabled: bool = True,
    priority: int = 100,
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
                source_id
            ),
            "kind": (
                "licensed_subscription"
            ),
            "enabled": enabled,
            "priority": priority,
            "max_connections": 1,
            "backend_reference": (
                f"dispatcharr:m3u:{account_id}"
            ),
        }
    )


def _stream(
    stream_id: int,
    name: str,
    account_id: int,
    *,
    group_name: str | None = "NFL",
    is_stale: bool = False,
) -> SafeDispatcharrStream:
    return SafeDispatcharrStream(
        stream_id=stream_id,
        name=name,
        m3u_account_id=account_id,
        group_name=group_name,
        is_stale=is_stale,
    )


class FakeDispatcharr:
    def __init__(
        self,
        streams_by_account: dict[
            int,
            tuple[SafeDispatcharrStream, ...],
        ],
    ) -> None:
        self.streams_by_account = (
            streams_by_account
        )
        self.calls: list[int] = []

    def list_streams(
        self,
        *,
        account_id: int,
    ) -> tuple[SafeDispatcharrStream, ...]:
        self.calls.append(account_id)
        return self.streams_by_account.get(
            account_id,
            (),
        )


def test_queries_each_eligible_account_once_and_resolves_content() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    175,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
            3: (
                _stream(
                    275,
                    "NFL Seattle Seahawks",
                    3,
                ),
                _stream(
                    276,
                    "NFL New England Patriots",
                    3,
                ),
            ),
        }
    )

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(
            _source(
                "primary",
                2,
                priority=200,
            ),
            _source(
                "fallback",
                3,
                priority=100,
            ),
        ),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert dispatcharr.calls == [2, 3]
    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.EXACT_EVENT
    )
    assert result.resource_source_ids == (
        "primary",
    )


def test_disabled_and_unrelated_sources_are_not_queried() -> None:
    disabled = _source(
        "disabled",
        2,
        enabled=False,
    )

    unrelated = SportsSource.from_mapping(
        {
            "source_id": "unrelated",
            "display_name": "Unrelated",
            "provider_id": "unrelated",
            "provider_display_name": (
                "Unrelated"
            ),
            "account_display_name": (
                "Unrelated"
            ),
            "kind": "official_free",
            "enabled": True,
            "priority": 100,
            "max_connections": 1,
            "backend_reference": (
                "other:backend:3"
            ),
        }
    )

    dispatcharr = FakeDispatcharr({})

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(
            disabled,
            unrelated,
        ),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert dispatcharr.calls == []
    assert result is None


def test_duplicate_account_reference_is_queried_once_but_resolver_fails_closed() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    175,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            "multiple enabled Sports "
            "sources reference the same "
            "Dispatcharr account"
        ),
    ):
        resolve_event_live_source_content(
            event=_event(),
            sources=(
                _source(
                    "one",
                    2,
                ),
                _source(
                    "two",
                    2,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )

    assert dispatcharr.calls == [2]


def test_legacy_numeric_account_reference_is_discovered() -> None:
    legacy = SportsSource.from_mapping(
        {
            "source_id": "legacy",
            "display_name": "Legacy",
            "provider_id": "legacy",
            "provider_display_name": "Legacy",
            "account_display_name": "Legacy",
            "kind": "licensed_subscription",
            "enabled": True,
            "priority": 100,
            "max_connections": 1,
            "backend_reference": "2",
        }
    )

    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    175,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(legacy,),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert dispatcharr.calls == [2]
    assert result is not None
    assert result.resource_source_ids == (
        "legacy",
    )


def test_authoritative_empty_streams_resolve_to_none() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (),
        }
    )

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(
            _source(
                "primary",
                2,
            ),
        ),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert dispatcharr.calls == [2]
    assert result is None


def test_dispatcharr_failure_is_not_converted_to_empty_state() -> None:
    class UnavailableDispatcharr:
        def list_streams(
            self,
            *,
            account_id: int,
        ) -> tuple[
            SafeDispatcharrStream,
            ...,
        ]:
            raise DispatcharrAdminError(
                "Dispatcharr unavailable"
            )

    with pytest.raises(
        DispatcharrAdminError,
        match="Dispatcharr unavailable",
    ):
        resolve_event_live_source_content(
            event=_event(),
            sources=(
                _source(
                    "primary",
                    2,
                ),
            ),
            dispatcharr=UnavailableDispatcharr(),  # type: ignore[arg-type]
        )


def test_safe_stream_metadata_is_forwarded_without_backend_secrets() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    175,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                    group_name="NFL",
                ),
            ),
        }
    )

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(
            _source(
                "primary",
                2,
            ),
        ),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert result is not None

    payload = result.to_mapping()
    rendered = repr(payload).casefold()

    assert "password" not in rendered
    assert "username" not in rendered
    assert "server_url" not in rendered
    assert "backend_reference" not in rendered
    assert "token" not in rendered



def test_build_provisioning_plan_uses_canonical_shared_event_identity() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    900,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    event = _event()

    resolution = (
        resolve_event_live_source_content(
            event=event,
            sources=(
                _source(
                    "primary",
                    2,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )
    )

    assert resolution is not None

    plan = (
        build_live_source_provisioning_plan(
            event=event,
            resolution=resolution,
        )
    )

    assert plan.source_id == (
        "thesportsdb-2475374"
    )

    assert plan.atlas_channel_id == (
        "sports-live-thesportsdb-2475374"
    )

    assert plan.name == (
        "Seattle Seahawks vs "
        "New England Patriots"
    )

    assert plan.provider == "thesportsdb"
    assert (
        plan.provider_event_id
        == "2475374"
    )

    assert plan.resource_source_ids == (
        "primary",
    )

    assert plan.stream_ids == (
        900,
    )


def test_build_provisioning_plan_preserves_ranked_source_and_stream_order() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
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
            ),
            3: (
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
            ),
        }
    )

    event = _event()

    resolution = (
        resolve_event_live_source_content(
            event=event,
            sources=(
                _source(
                    "later",
                    2,
                    priority=200,
                ),
                _source(
                    "first",
                    3,
                    priority=100,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )
    )

    assert resolution is not None
    assert resolution.resource_source_ids == (
        "first",
        "later",
    )

    plan = (
        build_live_source_provisioning_plan(
            event=event,
            resolution=resolution,
        )
    )

    assert [
        item.source_id
        for item
        in plan.source_streams
    ] == [
        "first",
        "later",
    ]

    assert [
        item.stream_ids
        for item
        in plan.source_streams
    ] == [
        (302, 301),
        (202, 201),
    ]

    assert plan.stream_ids == (
        302,
        301,
        202,
        201,
    )


def test_build_provisioning_plan_rejects_mismatched_event_identity() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    900,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    event = _event()

    resolution = (
        resolve_event_live_source_content(
            event=event,
            sources=(
                _source(
                    "primary",
                    2,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )
    )

    assert resolution is not None

    wrong_event = dict(event)
    wrong_event[
        "provider_event_id"
    ] = "different-event"

    with pytest.raises(
        ValueError,
        match=(
            "resolution event identity "
            "does not match event"
        ),
    ):
        build_live_source_provisioning_plan(
            event=wrong_event,
            resolution=resolution,
        )


def test_provisioning_plan_is_secret_and_url_free() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    900,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    event = _event()

    resolution = (
        resolve_event_live_source_content(
            event=event,
            sources=(
                _source(
                    "primary",
                    2,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )
    )

    assert resolution is not None

    plan = (
        build_live_source_provisioning_plan(
            event=event,
            resolution=resolution,
        )
    )

    rendered = repr(
        plan.to_mapping()
    ).casefold()

    for forbidden in (
        "password",
        "username",
        "server_url",
        "backend_reference",
        "access_token",
        "api_key",
        "http://",
        "https://",
    ):
        assert forbidden not in rendered
