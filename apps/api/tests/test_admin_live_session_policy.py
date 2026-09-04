from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from atlas.live_session_policy import LiveSessionPolicyStore
from atlas.user_profiles import UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_current_user,
    get_identity_writer_client,
    get_live_session_policy_store,
    get_security_audit_writer,
    get_user_profile_store,
)
from atlas_api.main import create_app


class RecordingWriter:
    def __init__(self) -> None:
        self.default_limits: list[int] = []
        self.overrides: list[tuple[str, int]] = []
        self.clears: list[str] = []

    def set_live_session_default_limit(self, limit: int) -> dict[str, object]:
        self.default_limits.append(limit)
        return {"default_limit": limit}

    def set_live_session_user_override(self, user_id: str, limit: int) -> dict[str, object]:
        self.overrides.append((user_id, limit))
        return {"user_id": user_id, "override_limit": limit}

    def clear_live_session_user_override(self, user_id: str) -> dict[str, object]:
        self.clears.append(user_id)
        return {"user_id": user_id, "override_limit": None}


class RecordingAudit:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any] | None]] = []

    def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append((event_name, dict(payload) if payload is not None else None))


def _authenticated(profile: dict[str, Any]) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=str(profile["user_id"]),
        username=str(profile["username"]),
        display_name=str(profile["display_name"]),
        roles=tuple(profile["roles"]),
        provider="atlas",
        metadata={},
    )


def _fixture(tmp_path: Path, *, role: str = "global_admin"):
    profiles = UserProfileStore(tmp_path / "users")
    admin = profiles.create_user(
        "atlas-admin",
        display_name="Atlas Admin",
        email="admin@example.test",
        roles=(role,),
    )
    target = profiles.create_user(
        "target-user",
        display_name="Target User",
        email="target@example.test",
        roles=("member",),
    )
    policy = LiveSessionPolicyStore(tmp_path / "users" / "live-session-policy.json")
    writer = RecordingWriter()
    audit = RecordingAudit()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _authenticated(admin)
    app.dependency_overrides[get_user_profile_store] = lambda: profiles
    app.dependency_overrides[get_live_session_policy_store] = lambda: policy
    app.dependency_overrides[get_identity_writer_client] = lambda: writer
    app.dependency_overrides[get_security_audit_writer] = lambda: audit
    return TestClient(app), policy, writer, audit, admin, target


def test_admin_policy_read_uses_default_without_creating_file(tmp_path: Path) -> None:
    client, policy, _, _, _, target = _fixture(tmp_path)
    assert not policy.path.exists()
    response = client.get("/api/v1/admin/live-sessions")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["default_limit"] == 5
    target_row = next(row for row in body["users"] if row["user_id"] == target["user_id"])
    assert target_row["override_limit"] is None
    assert target_row["effective_limit"] == 5
    assert not policy.path.exists()


def test_admin_can_update_default_and_user_override(tmp_path: Path) -> None:
    client, _, writer, audit, admin, target = _fixture(tmp_path)
    response = client.patch("/api/v1/admin/live-sessions/default", json={"limit": 6})
    assert response.status_code == 200
    assert response.json() == {"default_limit": 6}
    assert writer.default_limits == [6]

    response = client.put(
        f"/api/v1/admin/live-sessions/users/{target['user_id']}",
        json={"limit": 2},
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": target["user_id"], "override_limit": 2}
    assert writer.overrides == [(target["user_id"], 2)]
    assert audit.events == [
        (
            "security.live_sessions.default_limit_updated",
            {"actor_user_id": admin["user_id"], "default_limit": 6},
        ),
        (
            "security.live_sessions.user_override_updated",
            {
                "actor_user_id": admin["user_id"],
                "target_user_id": target["user_id"],
                "override_limit": 2,
            },
        ),
    ]


def test_default_action_clears_override_instead_of_copying_default(tmp_path: Path) -> None:
    client, _, writer, audit, admin, target = _fixture(tmp_path)
    response = client.delete(f"/api/v1/admin/live-sessions/users/{target['user_id']}")
    assert response.status_code == 200
    assert response.json() == {"user_id": target["user_id"], "override_limit": None}
    assert writer.clears == [target["user_id"]]
    assert audit.events == [
        (
            "security.live_sessions.user_override_cleared",
            {"actor_user_id": admin["user_id"], "target_user_id": target["user_id"]},
        )
    ]


def test_admin_policy_mutation_rejects_missing_target(tmp_path: Path) -> None:
    client, _, writer, audit, _, _ = _fixture(tmp_path)
    response = client.put(
        "/api/v1/admin/live-sessions/users/usr-missing",
        json={"limit": 2},
    )
    assert response.status_code == 404
    assert writer.overrides == []
    assert audit.events == []


def test_member_cannot_manage_live_session_policy(tmp_path: Path) -> None:
    client, policy, writer, audit, _, _ = _fixture(tmp_path, role="member")
    assert client.get("/api/v1/admin/live-sessions").status_code == 403
    assert client.patch(
        "/api/v1/admin/live-sessions/default",
        json={"limit": 9},
    ).status_code == 403
    assert not policy.path.exists()
    assert writer.default_limits == []
    assert len(audit.events) == 2
    assert all(
        event_name == "security.authorization.denied"
        for event_name, _ in audit.events
    )
    assert all(
        payload is not None
        and payload.get("permission") == "atlas.live_sessions.manage"
        and payload.get("reason") == "missing_grant"
        for _, payload in audit.events
    )
    assert not any(
        event_name.startswith("security.live_sessions.")
        for event_name, _ in audit.events
    )


def test_atlas_admin_can_manage_live_session_policy(tmp_path: Path) -> None:
    client, _, writer, _, _, _ = _fixture(tmp_path, role="atlas_admin")
    response = client.patch("/api/v1/admin/live-sessions/default", json={"limit": 8})
    assert response.status_code == 200
    assert writer.default_limits == [8]


def test_invalid_limits_are_rejected_before_writer(tmp_path: Path) -> None:
    client, _, writer, _, _, _ = _fixture(tmp_path)
    for value in (0, -1, True, "2"):
        response = client.patch(
            "/api/v1/admin/live-sessions/default",
            json={"limit": value},
        )
        assert response.status_code == 422
    assert writer.default_limits == []
