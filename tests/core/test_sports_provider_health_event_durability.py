from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPORTS_SRC = ROOT / "modules" / "sports" / "src"


def _worker():
    path = str(SPORTS_SRC)

    if path not in sys.path:
        sys.path.insert(
            0,
            path,
        )

    sys.modules.pop(
        "worker",
        None,
    )

    return importlib.import_module(
        "worker"
    )


def _provider_result(
    events=(),
):
    return {
        "previous_games": {},
        "subscribed_previous_games": {},
        "provider_games": [],
        "provider_health": {
            "thesportsdb": {
                "status": "healthy",
                "game_count": 16,
            }
        },
        "subscribed_games": [],
        "degraded_count": 0,
        "provider_health_events": tuple(
            events
        ),
    }


def _stub_successful_operations(
    worker,
    monkeypatch: pytest.MonkeyPatch,
    order: list[str],
) -> None:
    monkeypatch.setattr(
        worker,
        "prune_unmanaged_games",
        lambda *_args, **_kwargs: 0,
    )

    monkeypatch.setattr(
        worker,
        "process_games",
        lambda *_args, **_kwargs: {},
    )

    monkeypatch.setattr(
        worker,
        "run_live_source_provisioning_pipeline",
        lambda *_args, **_kwargs: (
            order.append("provision")
            or 0
        ),
    )

    monkeypatch.setattr(
        worker,
        "generate_feed_snapshot",
        lambda: (
            order.append("feed")
            or (0, ())
        ),
    )

    monkeypatch.setattr(
        worker,
        "refresh_jellyfin_live_tv",
        lambda: order.append(
            "refresh"
        ),
    )

    monkeypatch.setattr(
        worker,
        "converge_jellyfin_live_tv_bindings",
        lambda _channel_ids: (
            order.append("bind")
        ),
    )

    monkeypatch.setattr(
        worker,
        "write_heartbeat",
        lambda: order.append(
            "heartbeat"
        ),
    )

    monkeypatch.setattr(
        worker,
        "write_health_report",
        lambda: (
            order.append("health-report")
            or {"status": "healthy"}
        ),
    )

    monkeypatch.setattr(
        worker,
        "recording_counts",
        lambda _recordings: {
            "pending": 0,
            "active": 0,
            "completed": 0,
        },
    )


def test_provider_transition_markers_do_not_publish_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    published = []

    monkeypatch.setattr(
        worker,
        "publish_provider_health_event",
        lambda *args: published.append(
            args
        ),
    )

    recovered_health = {
        "thesportsdb": {
            "status": "degraded",
            "last_failure_at": "earlier",
            "game_count": 16,
        }
    }

    recovered = worker.mark_provider_healthy(
        recovered_health,
        "thesportsdb",
        16,
    )

    degraded_health = {
        "thesportsdb": {
            "status": "healthy",
            "last_success_at": "earlier",
            "game_count": 16,
        }
    }

    degraded = worker.mark_provider_degraded(
        degraded_health,
        "thesportsdb",
        RuntimeError(
            "synthetic provider failure"
        ),
    )

    assert recovered is not None
    assert recovered[0] == (
        "sports.provider-recovered"
    )

    assert degraded is not None
    assert degraded[0] == (
        "sports.provider-degraded"
    )

    assert published == []


def test_provider_transition_publishes_after_durable_health_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()
    order: list[str] = []

    _stub_successful_operations(
        worker,
        monkeypatch,
        order,
    )

    monkeypatch.setattr(
        worker,
        "write_provider_health",
        lambda _health: order.append(
            "provider-health"
        ),
    )

    monkeypatch.setattr(
        worker,
        "publish_provider_health_event",
        lambda event_name, _payload: (
            order.append(
                f"event:{event_name}"
            )
        ),
    )

    result = worker.run_operations_pipeline(
        _provider_result(
            (
                (
                    "sports.provider-recovered",
                    {
                        "provider": "thesportsdb",
                        "status": "healthy",
                    },
                ),
            )
        ),
        {},
    )

    assert result == 0

    assert order.index(
        "provider-health"
    ) < order.index(
        "event:sports.provider-recovered"
    )

    assert order.index(
        "event:sports.provider-recovered"
    ) < order.index(
        "heartbeat"
    )


def test_downstream_failure_emits_no_uncommitted_provider_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()

    writes = []
    published = []

    monkeypatch.setattr(
        worker,
        "prune_unmanaged_games",
        lambda *_args, **_kwargs: 0,
    )

    monkeypatch.setattr(
        worker,
        "process_games",
        lambda *_args, **_kwargs: {},
    )

    def fail_provisioning(
        *_args,
        **_kwargs,
    ):
        raise RuntimeError(
            "synthetic dispatcharr failure"
        )

    monkeypatch.setattr(
        worker,
        "run_live_source_provisioning_pipeline",
        fail_provisioning,
    )

    monkeypatch.setattr(
        worker,
        "write_provider_health",
        lambda _health: writes.append(
            "provider-health"
        ),
    )

    monkeypatch.setattr(
        worker,
        "publish_provider_health_event",
        lambda *args: published.append(
            args
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic dispatcharr failure",
    ):
        worker.run_operations_pipeline(
            _provider_result(
                (
                    (
                        "sports.provider-recovered",
                        {
                            "provider": (
                                "thesportsdb"
                            ),
                            "status": "healthy",
                        },
                    ),
                )
            ),
            {},
        )

    assert writes == []
    assert published == []
