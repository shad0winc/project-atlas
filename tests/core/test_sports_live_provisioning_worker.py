from __future__ import annotations

import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPORTS_SRC = ROOT / "modules" / "sports" / "src"


def _worker():
    path = str(SPORTS_SRC)
    if path not in sys.path:
        sys.path.insert(0, path)

    sys.modules.pop("worker", None)
    return importlib.import_module("worker")


def _live_game(
    game_id: str = "game-1",
) -> dict[str, object]:
    return {
        "id": game_id,
        "provider": "thesportsdb",
        "provider_event_id": "event-1",
        "name": "Atlas One vs Atlas Two",
        "lifecycle_state": "live",
        "status": "live",
        "start_at": "2026-09-11T00:00:00Z",
    }


def test_outside_pregame_window_does_not_resolve_or_mutate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    now = datetime(
        2026,
        9,
        11,
        12,
        0,
        tzinfo=timezone.utc,
    )

    game = {
        "id": "game-future",
        "provider": "thesportsdb",
        "provider_event_id": "future-event",
        "name": "Future Game",
        "lifecycle_state": "scheduled",
        "status": "scheduled",
        "start_at": (
            now + timedelta(hours=4)
        ).isoformat(),
    }

    def unexpected(*args, **kwargs):
        raise AssertionError(
            "content resolution must not run "
            "outside the visibility window"
        )

    monkeypatch.setattr(
        worker,
        "resolve_event_live_source_content",
        unexpected,
    )

    result = worker.run_live_source_provisioning_pipeline(
        [game],
        now=now,
        dispatcharr=object(),
        sources=(object(),),
        bindings=object(),
    )

    assert result == 0


def test_surfaced_game_resolves_plans_and_reconciles_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    resolution = object()
    plan = object()
    channel = object()
    published_source = object()
    dispatcharr = object()
    bindings = object()
    live_sources = object()
    sources = (object(),)
    calls: list[tuple[str, object]] = []

    def resolve(*, event, sources, dispatcharr):
        calls.append(("resolve-event", event))
        calls.append(("resolve-sources", sources))
        calls.append(("resolve-dispatcharr", dispatcharr))
        return resolution

    def build(*, event, resolution):
        calls.append(("build-event", event))
        calls.append(("build-resolution", resolution))
        return plan

    def reconcile(*, plan, dispatcharr, bindings):
        calls.append(("reconcile-plan", plan))
        calls.append(("reconcile-dispatcharr", dispatcharr))
        calls.append(("reconcile-bindings", bindings))
        return channel, object()

    def publish(*, plan, channel, dispatcharr_base_url):
        calls.append(("publish-plan", plan))
        calls.append(("publish-channel", channel))
        calls.append(
            ("publish-base-url", dispatcharr_base_url)
        )
        return published_source

    class Registry:
        def set(self, source):
            calls.append(("registry-set", source))
            return source

    monkeypatch.setattr(
        worker,
        "resolve_event_live_source_content",
        resolve,
    )
    monkeypatch.setattr(
        worker,
        "build_live_source_provisioning_plan",
        build,
    )
    monkeypatch.setattr(
        worker,
        "reconcile_dispatcharr_channel",
        reconcile,
    )
    monkeypatch.setattr(
        worker,
        "build_published_live_source",
        publish,
    )

    live_sources = Registry()

    game = _live_game()

    result = worker.run_live_source_provisioning_pipeline(
        [game],
        now=datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        dispatcharr=dispatcharr,
        sources=sources,
        bindings=bindings,
        live_sources=live_sources,
    )

    assert result == 1
    assert calls == [
        ("resolve-event", game),
        ("resolve-sources", sources),
        ("resolve-dispatcharr", dispatcharr),
        ("build-event", game),
        ("build-resolution", resolution),
        ("reconcile-plan", plan),
        ("reconcile-dispatcharr", dispatcharr),
        ("reconcile-bindings", bindings),
        ("publish-plan", plan),
        ("publish-channel", channel),
        (
            "publish-base-url",
            "http://atlas-dispatcharr:9191",
        ),
        ("registry-set", published_source),
    ]


def test_no_content_resolution_means_no_channel_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    monkeypatch.setattr(
        worker,
        "resolve_event_live_source_content",
        lambda **kwargs: None,
    )

    def unexpected(*args, **kwargs):
        raise AssertionError(
            "channel reconciliation must not run "
            "without authorized content"
        )

    monkeypatch.setattr(
        worker,
        "build_live_source_provisioning_plan",
        unexpected,
    )
    monkeypatch.setattr(
        worker,
        "reconcile_dispatcharr_channel",
        unexpected,
    )

    result = worker.run_live_source_provisioning_pipeline(
        [_live_game()],
        now=datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        dispatcharr=object(),
        sources=(object(),),
        bindings=object(),
    )

    assert result == 0


def test_empty_source_lifecycle_does_not_construct_dispatcharr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    class Store:
        def load(self):
            return ()

    class Client:
        @classmethod
        def from_environment(cls):
            raise AssertionError(
                "Dispatcharr client must not be constructed "
                "when there are no authorized sources"
            )

    monkeypatch.setattr(
        worker,
        "SourceLifecycleStore",
        Store,
    )
    monkeypatch.setattr(
        worker,
        "DispatcharrAdminClient",
        Client,
    )

    result = worker.run_live_source_provisioning_pipeline(
        [_live_game()],
        now=datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert result == 0


def test_reconciliation_failure_propagates_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    monkeypatch.setattr(
        worker,
        "resolve_event_live_source_content",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        worker,
        "build_live_source_provisioning_plan",
        lambda **kwargs: object(),
    )

    def fail(**kwargs):
        raise RuntimeError(
            "synthetic reconciliation failure"
        )

    monkeypatch.setattr(
        worker,
        "reconcile_dispatcharr_channel",
        fail,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic reconciliation failure",
    ):
        worker.run_live_source_provisioning_pipeline(
            [_live_game()],
            now=datetime(
                2026,
                9,
                11,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            dispatcharr=object(),
            sources=(object(),),
            bindings=object(),
        )


def test_operations_provisions_only_current_subscribed_games(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    current = _live_game("current-game")
    preserved = _live_game("preserved-game")

    provider_result = {
        "previous_games": {},
        "subscribed_previous_games": {},
        "provider_games": [current],
        "provider_health": {},
        "subscribed_games": [current],
        "degraded_count": 0,
    }

    monkeypatch.setattr(
        worker,
        "prune_unmanaged_games",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        worker,
        "process_games",
        lambda games: {
            "current-game": current,
            "preserved-game": preserved,
        },
    )

    seen: list[list[str]] = []

    def provision(games):
        seen.append(
            [str(game["id"]) for game in games]
        )
        return 1

    monkeypatch.setattr(
        worker,
        "run_live_source_provisioning_pipeline",
        provision,
    )
    monkeypatch.setattr(
        worker,
        "write_provider_health",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        worker,
        "write_heartbeat",
        lambda: None,
    )
    monkeypatch.setattr(
        worker,
        "write_health_report",
        lambda: {"status": "healthy"},
    )
    monkeypatch.setattr(
        worker,
        "recording_counts",
        lambda recordings: {
            "pending": 0,
            "active": 0,
            "completed": 0,
        },
    )

    result = worker.run_operations_pipeline(
        provider_result,
        {},
    )

    assert result == 0
    assert seen == [["current-game"]]


def test_controller_compose_exposes_required_runtime_contract() -> None:
    source = (
        ROOT
        / "modules"
        / "sports"
        / "docker-compose.yml"
    ).read_text(encoding="utf-8")

    controller = source.split(
        "  atlas-sports-controller:\n",
        1,
    )[1].split(
        "\nnetworks:",
        1,
    )[0]

    for key in (
        "SPORTS_DISPATCHARR_CHANNEL_BINDINGS_FILE:",
        "SPORTS_SOURCE_LIFECYCLE_FILE:",
        "SPORTS_PREGAME_WINDOW_MINUTES:",
        "DISPATCHARR_INTERNAL_URL:",
        "DISPATCHARR_ADMIN_USERNAME:",
        "DISPATCHARR_ADMIN_PASSWORD:",
    ):
        assert key in controller


def test_module_contract_requires_provisioning_dependencies() -> None:
    source = (
        ROOT
        / "modules"
        / "sports"
        / "module.conf"
    ).read_text(encoding="utf-8")

    for path in (
        "src/dispatcharr_admin.py",
        "src/dispatcharr_channel_bindings.py",
        "src/live_source_resolver.py",
        "src/live_source_orchestration.py",
    ):
        assert path in source



def test_dispatcharr_failure_never_publishes_live_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    monkeypatch.setattr(
        worker,
        "resolve_event_live_source_content",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        worker,
        "build_live_source_provisioning_plan",
        lambda **kwargs: object(),
    )

    def fail_reconcile(**kwargs):
        raise RuntimeError(
            "synthetic dispatcharr failure"
        )

    monkeypatch.setattr(
        worker,
        "reconcile_dispatcharr_channel",
        fail_reconcile,
    )

    def unexpected_publish(**kwargs):
        raise AssertionError(
            "LiveSource must not be built after "
            "Dispatcharr reconciliation failure"
        )

    monkeypatch.setattr(
        worker,
        "build_published_live_source",
        unexpected_publish,
    )

    class Registry:
        def set(self, source):
            raise AssertionError(
                "LiveSource registry must not mutate "
                "after Dispatcharr failure"
            )

    with pytest.raises(
        RuntimeError,
        match="synthetic dispatcharr failure",
    ):
        worker.run_live_source_provisioning_pipeline(
            [_live_game()],
            now=datetime(
                2026,
                9,
                11,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            dispatcharr=object(),
            sources=(object(),),
            bindings=object(),
            live_sources=Registry(),
        )


def test_live_source_persistence_failure_propagates_after_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    resolution = object()
    plan = object()
    channel = object()
    source = object()

    monkeypatch.setattr(
        worker,
        "resolve_event_live_source_content",
        lambda **kwargs: resolution,
    )
    monkeypatch.setattr(
        worker,
        "build_live_source_provisioning_plan",
        lambda **kwargs: plan,
    )
    monkeypatch.setattr(
        worker,
        "reconcile_dispatcharr_channel",
        lambda **kwargs: (channel, object()),
    )
    monkeypatch.setattr(
        worker,
        "build_published_live_source",
        lambda **kwargs: source,
    )

    class Registry:
        def set(self, value):
            assert value is source
            raise RuntimeError(
                "synthetic LiveSource persistence failure"
            )

    with pytest.raises(
        RuntimeError,
        match="synthetic LiveSource persistence failure",
    ):
        worker.run_live_source_provisioning_pipeline(
            [_live_game()],
            now=datetime(
                2026,
                9,
                11,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            dispatcharr=object(),
            sources=(object(),),
            bindings=object(),
            live_sources=Registry(),
        )


def test_no_authorized_content_does_not_touch_live_source_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    monkeypatch.setattr(
        worker,
        "resolve_event_live_source_content",
        lambda **kwargs: None,
    )

    class Registry:
        def set(self, source):
            raise AssertionError(
                "LiveSource registry must not mutate "
                "without authorized content"
            )

    result = worker.run_live_source_provisioning_pipeline(
        [_live_game()],
        now=datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        dispatcharr=object(),
        sources=(object(),),
        bindings=object(),
        live_sources=Registry(),
    )

    assert result == 0
