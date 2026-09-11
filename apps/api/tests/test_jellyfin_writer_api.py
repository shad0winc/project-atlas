from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from atlas.media.jellyfin_admin import (
    JellyfinAdminError,
    JellyfinScheduledTask,
)


TOKEN = "jellyfin-writer-test-token"


class _AdminDouble:
    def __init__(
        self,
        *,
        initial_state: str = "Idle",
        poll_states: tuple[str, ...] = ("Running", "Idle"),
    ) -> None:
        self.initial_state = initial_state
        self.poll_states = list(poll_states)
        self.keys: list[str] = []
        self.started: list[str] = []
        self.lookups: list[str] = []

    def find_scheduled_task_by_key(
        self,
        key: str,
    ) -> JellyfinScheduledTask:
        self.keys.append(key)
        return JellyfinScheduledTask(
            task_id="task-guide",
            key=key,
            name="Refresh Guide",
            state=self.initial_state,
        )

    def start_scheduled_task(
        self,
        task_id: str,
    ) -> None:
        self.started.append(task_id)

    def get_scheduled_task(
        self,
        task_id: str,
    ) -> JellyfinScheduledTask:
        self.lookups.append(task_id)

        state = (
            self.poll_states.pop(0)
            if self.poll_states
            else "Idle"
        )

        return JellyfinScheduledTask(
            task_id=task_id,
            key="RefreshGuide",
            name="Refresh Guide",
            state=state,
        )


def _load_writer(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_WRITER_TOKEN",
        TOKEN,
    )
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_URL",
        "http://jellyfin:8096",
    )
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_API_KEY",
        "test-jellyfin-api-key",
    )
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_TIMEOUT_SECONDS",
        "10",
    )

    module = importlib.import_module(
        "atlas_api.jellyfin_writer"
    )
    return importlib.reload(module)


def _auth() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
    }


def test_health_is_public_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_writer(monkeypatch)
    response = TestClient(module.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
    }


def test_missing_and_invalid_service_tokens_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_writer(monkeypatch)
    client = TestClient(module.app)

    endpoint = (
        "/internal/v1/jellyfin/live-tv/refresh"
    )

    assert client.post(endpoint).status_code == 401
    assert client.post(
        endpoint,
        headers={
            "Authorization": "Bearer wrong-token",
        },
    ).status_code == 401


def test_refresh_uses_only_exact_refresh_guide_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_writer(monkeypatch)
    admin = _AdminDouble()

    monkeypatch.setattr(
        module,
        "_jellyfin_admin_client",
        lambda: admin,
    )
    monkeypatch.setattr(
        module,
        "REFRESH_POLL_SECONDS",
        0.001,
    )

    response = TestClient(module.app).post(
        "/internal/v1/jellyfin/live-tv/refresh",
        headers=_auth(),
        json={
            "task_key": "DoNotRunThisTask",
            "task_id": "arbitrary-task",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "task_key": "RefreshGuide",
    }
    assert admin.keys == ["RefreshGuide"]
    assert admin.started == ["task-guide"]
    assert admin.lookups == [
        "task-guide",
        "task-guide",
    ]


def test_non_idle_task_fails_before_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_writer(monkeypatch)
    admin = _AdminDouble(
        initial_state="Running",
    )

    monkeypatch.setattr(
        module,
        "_jellyfin_admin_client",
        lambda: admin,
    )

    response = TestClient(module.app).post(
        "/internal/v1/jellyfin/live-tv/refresh",
        headers=_auth(),
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Jellyfin Live TV refresh is not idle.",
    }
    assert admin.started == []
    assert admin.lookups == []


def test_writer_serializes_refresh_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_writer(monkeypatch)

    assert module._REFRESH_LOCK.acquire(
        blocking=False
    )

    try:
        response = TestClient(module.app).post(
            "/internal/v1/jellyfin/live-tv/refresh",
            headers=_auth(),
        )
    finally:
        module._REFRESH_LOCK.release()

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Jellyfin Live TV refresh is already active."
        ),
    }


def test_unexpected_task_state_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_writer(monkeypatch)
    admin = _AdminDouble(
        poll_states=("Cancelling",),
    )

    monkeypatch.setattr(
        module,
        "_jellyfin_admin_client",
        lambda: admin,
    )

    response = TestClient(module.app).post(
        "/internal/v1/jellyfin/live-tv/refresh",
        headers=_auth(),
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Jellyfin Live TV refresh failed.",
    }


def test_upstream_jellyfin_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_writer(monkeypatch)

    class _FailingAdmin:
        def find_scheduled_task_by_key(
            self,
            _key: str,
        ):
            raise JellyfinAdminError(
                "secret upstream detail",
                status_code=500,
            )

    monkeypatch.setattr(
        module,
        "_jellyfin_admin_client",
        lambda: _FailingAdmin(),
    )

    response = TestClient(module.app).post(
        "/internal/v1/jellyfin/live-tv/refresh",
        headers=_auth(),
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Jellyfin Live TV refresh failed.",
    }
    assert "secret upstream detail" not in response.text


def test_bounded_refresh_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_writer(monkeypatch)
    admin = _AdminDouble(
        poll_states=("Running", "Running"),
    )

    clock = iter((0.0, 2.0))

    with pytest.raises(
        module.JellyfinLiveTvRefreshTimeoutError
    ):
        module._refresh_live_tv(
            admin,
            timeout_seconds=1.0,
            poll_seconds=0.1,
            monotonic=lambda: next(clock),
            sleep=lambda _seconds: None,
        )

    assert admin.started == ["task-guide"]
