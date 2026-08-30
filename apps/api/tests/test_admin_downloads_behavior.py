from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.routes.v1 import admin_downloads


JOB_ID = "dl_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class _Writer:
    def __init__(self) -> None:
        self.calls = []

    def mutate(self, job_id: str, action: str):
        self.calls.append((job_id, action))
        return {"status": "accepted", "job_id": job_id, "action": action}


class _Audit:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event: str, payload) -> None:
        self.events.append((event, dict(payload)))


def _app(writer: _Writer, audit: _Audit) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_downloads.router, prefix="/api/v1")
    app.dependency_overrides[admin_downloads.require_downloads_manage] = lambda: AuthenticatedUser(
        user_id="usr_admin",
        username="admin",
        display_name="Admin",
        roles=("operator",),
        provider="test",
        metadata={},
    )
    app.dependency_overrides[admin_downloads.get_downloads_writer_client] = lambda: writer
    app.dependency_overrides[admin_downloads.get_security_audit_writer] = lambda: audit
    return app


def test_success_delegates_and_audits() -> None:
    writer = _Writer()
    audit = _Audit()
    response = TestClient(_app(writer, audit)).post(
        "/api/v1/admin/downloads/action",
        json={"job_id": JOB_ID, "action": "stop_seeding"},
    )
    assert response.status_code == 200
    assert writer.calls == [(JOB_ID, "stop_seeding")]
    assert audit.events[0][0] == "security.downloads.admin_action"
    assert audit.events[0][1]["job_id"] == JOB_ID


def test_invalid_job_is_rejected_before_writer() -> None:
    writer = _Writer()
    audit = _Audit()
    response = TestClient(_app(writer, audit)).post(
        "/api/v1/admin/downloads/action",
        json={"job_id": "not-opaque", "action": "resume"},
    )
    assert response.status_code == 400
    assert writer.calls == []
    assert audit.events == []


def test_delete_files_action_is_not_exposed() -> None:
    writer = _Writer()
    audit = _Audit()
    response = TestClient(_app(writer, audit)).post(
        "/api/v1/admin/downloads/action",
        json={"job_id": JOB_ID, "action": "delete_files"},
    )
    assert response.status_code == 400
    assert writer.calls == []
    assert audit.events == []
