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
    order: list[str] = []

    def process(games, *, publish_feed):
        assert publish_feed is False
        order.append("process")
        return {
            "current-game": current,
            "preserved-game": preserved,
        }

    monkeypatch.setattr(
        worker,
        "process_games",
        process,
    )

    seen: list[list[str]] = []

    def provision(games):
        order.append("provision")
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
        "generate_feed_snapshot",
        lambda: (
            order.append("feed")
            or (
                0,
                ("sports-live-current",),
            )
        ),
    )
    monkeypatch.setattr(
        worker,
        "refresh_jellyfin_live_tv",
        lambda: order.append("refresh"),
    )
    monkeypatch.setattr(
        worker,
        "converge_jellyfin_live_tv_bindings",
        lambda channel_ids: (
            order.append("bind")
        ),
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
    assert order == [
        "process",
        "provision",
        "feed",
        "refresh",
        "bind",
    ]


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



def test_operations_do_not_generate_feed_when_provisioning_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    current = _live_game("current-game")

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

    def process(games, *, publish_feed):
        assert publish_feed is False
        return {
            "current-game": current,
        }

    monkeypatch.setattr(
        worker,
        "process_games",
        process,
    )

    def fail_provision(games):
        raise RuntimeError(
            "synthetic provisioning failure"
        )

    monkeypatch.setattr(
        worker,
        "run_live_source_provisioning_pipeline",
        fail_provision,
    )

    def unexpected_feed():
        raise AssertionError(
            "feed must not regenerate after "
            "LiveSource provisioning failure"
        )

    monkeypatch.setattr(
        worker,
        "generate_feed_snapshot",
        unexpected_feed,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic provisioning failure",
    ):
        worker.run_operations_pipeline(
            provider_result,
            {},
        )


def test_operations_propagate_feed_generation_failure_after_provisioning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    current = _live_game("current-game")

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
        lambda games, *, publish_feed: {
            "current-game": current,
        },
    )
    monkeypatch.setattr(
        worker,
        "run_live_source_provisioning_pipeline",
        lambda games: 1,
    )
    monkeypatch.setattr(
        worker,
        "generate_feed_snapshot",
        lambda: (1, ()),
    )

    with pytest.raises(
        RuntimeError,
        match="Sports feed generation failed",
    ):
        worker.run_operations_pipeline(
            provider_result,
            {},
        )


def test_binding_plan_matches_exact_numeric_identity() -> None:
    worker = _worker()

    atlas_id = "sports-live-authorized-game"

    expected_number = (
        worker.atlas_jellyfin_channel_number(
            atlas_id
        )
    )

    result = (
        worker.build_jellyfin_live_tv_binding_plan(
            (atlas_id,),
            (
                worker.JellyfinLiveTvChannel(
                    item_id="jellyfin-exact",
                    channel_number=expected_number,
                ),
                worker.JellyfinLiveTvChannel(
                    item_id="jellyfin-other",
                    channel_number="900000001",
                ),
            ),
        )
    )

    assert result == {
        atlas_id: "jellyfin-exact"
    }


def test_binding_plan_fails_when_numeric_identity_is_missing() -> None:
    worker = _worker()

    with pytest.raises(
        worker.JellyfinLiveTvBindingConvergenceError,
        match="missing",
    ):
        worker.build_jellyfin_live_tv_binding_plan(
            ("sports-live-missing",),
            (),
        )


def test_binding_plan_fails_when_numeric_identity_is_ambiguous() -> None:
    worker = _worker()

    atlas_id = "sports-live-ambiguous"

    expected_number = (
        worker.atlas_jellyfin_channel_number(
            atlas_id
        )
    )

    with pytest.raises(
        worker.JellyfinLiveTvBindingConvergenceError,
        match="ambiguous",
    ):
        worker.build_jellyfin_live_tv_binding_plan(
            (atlas_id,),
            (
                worker.JellyfinLiveTvChannel(
                    item_id="jellyfin-one",
                    channel_number=expected_number,
                ),
                worker.JellyfinLiveTvChannel(
                    item_id="jellyfin-two",
                    channel_number=expected_number,
                ),
            ),
        )


def test_binding_plan_fails_on_projected_number_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    monkeypatch.setattr(
        worker,
        "atlas_jellyfin_channel_number",
        lambda _atlas_id: "900000001",
    )

    with pytest.raises(
        worker.JellyfinLiveTvBindingConvergenceError,
        match="collision",
    ):
        worker.build_jellyfin_live_tv_binding_plan(
            (
                "sports-live-one",
                "sports-live-two",
            ),
            (),
        )


def test_binding_plan_rejects_duplicate_atlas_identity() -> None:
    worker = _worker()

    with pytest.raises(
        worker.JellyfinLiveTvBindingConvergenceError,
        match="duplicated",
    ):
        worker.build_jellyfin_live_tv_binding_plan(
            (
                "sports-live-one",
                "sports-live-one",
            ),
            (),
        )


def test_convergence_preflights_then_performs_one_batch_write() -> None:
    worker = _worker()

    atlas_one = "sports-live-one"
    atlas_two = "sports-live-two"

    number_one = (
        worker.atlas_jellyfin_channel_number(
            atlas_one
        )
    )
    number_two = (
        worker.atlas_jellyfin_channel_number(
            atlas_two
        )
    )

    calls: list[object] = []

    class Client:
        def list_live_tv_channels(self):
            calls.append("inventory")

            return (
                worker.JellyfinLiveTvChannel(
                    item_id="jellyfin-one",
                    channel_number=number_one,
                ),
                worker.JellyfinLiveTvChannel(
                    item_id="jellyfin-two",
                    channel_number=number_two,
                ),
            )

    class Registry:
        def set_many(self, proposed):
            calls.append(
                ("set-many", dict(proposed))
            )

    result = worker.converge_jellyfin_live_tv_bindings(
        (
            atlas_one,
            atlas_two,
        ),
        client=Client(),
        bindings=Registry(),
    )

    assert result == 2
    assert calls == [
        "inventory",
        (
            "set-many",
            {
                atlas_one: "jellyfin-one",
                atlas_two: "jellyfin-two",
            },
        ),
    ]


def test_ambiguous_inventory_never_writes_binding_batch() -> None:
    worker = _worker()

    atlas_id = "sports-live-one"

    number = (
        worker.atlas_jellyfin_channel_number(
            atlas_id
        )
    )

    class Client:
        def list_live_tv_channels(self):
            return (
                worker.JellyfinLiveTvChannel(
                    item_id="jellyfin-one",
                    channel_number=number,
                ),
                worker.JellyfinLiveTvChannel(
                    item_id="jellyfin-two",
                    channel_number=number,
                ),
            )

    class Registry:
        def set_many(self, _proposed):
            raise AssertionError(
                "binding state must not mutate "
                "after ambiguous inventory"
            )

    with pytest.raises(
        worker.JellyfinLiveTvBindingConvergenceError,
        match="ambiguous",
    ):
        worker.converge_jellyfin_live_tv_bindings(
            (atlas_id,),
            client=Client(),
            bindings=Registry(),
        )


def test_empty_published_feed_skips_inventory_and_binding_write() -> None:
    worker = _worker()

    class Client:
        def list_live_tv_channels(self):
            raise AssertionError(
                "empty published feed must not read inventory"
            )

    class Registry:
        def set_many(self, _proposed):
            raise AssertionError(
                "empty published feed must not write bindings"
            )

    assert (
        worker.converge_jellyfin_live_tv_bindings(
            (),
            client=Client(),
            bindings=Registry(),
        )
        == 0
    )


def test_binding_failure_occurs_before_provider_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    current = _live_game(
        "current-game"
    )

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
        lambda games, *, publish_feed: {
            "current-game": current,
        },
    )
    monkeypatch.setattr(
        worker,
        "run_live_source_provisioning_pipeline",
        lambda games: 1,
    )
    monkeypatch.setattr(
        worker,
        "generate_feed_snapshot",
        lambda: (
            0,
            ("sports-live-current",),
        ),
    )
    monkeypatch.setattr(
        worker,
        "refresh_jellyfin_live_tv",
        lambda: None,
    )

    def fail_binding(_channel_ids):
        raise RuntimeError(
            "synthetic binding convergence failure"
        )

    monkeypatch.setattr(
        worker,
        "converge_jellyfin_live_tv_bindings",
        fail_binding,
    )

    def unexpected_health(*_args, **_kwargs):
        raise AssertionError(
            "provider health must not publish after "
            "binding convergence failure"
        )

    monkeypatch.setattr(
        worker,
        "write_provider_health",
        unexpected_health,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic binding convergence failure",
    ):
        worker.run_operations_pipeline(
            provider_result,
            {},
        )
