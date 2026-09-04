from __future__ import annotations

import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

TOKEN = "test-live-session-policy-writer-token"


def _load_writer(monkeypatch, tmp_path: Path):
    users = tmp_path / "users"
    identity = tmp_path / "identity"
    monkeypatch.setenv("ATLAS_IDENTITY_WRITER_TOKEN", TOKEN)
    monkeypatch.setenv("ATLAS_USERS_DIR", str(users))
    monkeypatch.setenv("ATLAS_IDENTITY_DIR", str(identity))
    monkeypatch.setenv(
        "ATLAS_CUSTOM_ROLES_PATH",
        str(identity / "custom_roles" / "custom_roles.json"),
    )
    import atlas_api.identity_writer as module
    return importlib.reload(module), users


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_private_writer_policy_mutations_create_durable_state(monkeypatch, tmp_path: Path) -> None:
    module, users = _load_writer(monkeypatch, tmp_path)
    client = TestClient(module.app)
    policy = users / "live-session-policy.json"
    assert not policy.exists()

    response = client.patch(
        "/internal/v1/live-session-policy/default",
        headers=_headers(),
        json={"limit": 7},
    )
    assert response.status_code == 200
    assert response.json() == {"default_limit": 7}
    assert policy.exists()
    assert policy.stat().st_mode & 0o777 == 0o640

    response = client.put(
        "/internal/v1/live-session-policy/users/usr-one",
        headers=_headers(),
        json={"limit": 2},
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": "usr-one", "override_limit": 2}
    payload = json.loads(policy.read_text(encoding="utf-8"))
    assert payload == {
        "version": 1,
        "default_limit": 7,
        "overrides": {"usr-one": 2},
    }

    response = client.delete(
        "/internal/v1/live-session-policy/users/usr-one",
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": "usr-one", "override_limit": None}
    payload = json.loads(policy.read_text(encoding="utf-8"))
    assert payload["default_limit"] == 7
    assert payload["overrides"] == {}


def test_private_writer_policy_requires_service_token(monkeypatch, tmp_path: Path) -> None:
    module, _ = _load_writer(monkeypatch, tmp_path)
    response = TestClient(module.app).patch(
        "/internal/v1/live-session-policy/default",
        json={"limit": 4},
    )
    assert response.status_code in {401, 403}


def test_private_writer_policy_rejects_invalid_limit(monkeypatch, tmp_path: Path) -> None:
    module, users = _load_writer(monkeypatch, tmp_path)
    response = TestClient(module.app).patch(
        "/internal/v1/live-session-policy/default",
        headers=_headers(),
        json={"limit": 0},
    )
    assert response.status_code == 400
    assert not (users / "live-session-policy.json").exists()
