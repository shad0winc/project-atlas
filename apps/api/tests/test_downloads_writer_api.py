from __future__ import annotations

import importlib
import json
from urllib.parse import parse_qs

import pytest
from fastapi.testclient import TestClient

from atlas.downloads import opaque_job_id


TOKEN = "downloads-writer-test-token"
JOB_KEY = "downloads-job-id-test-key"
TORRENT_HASH = "0123456789abcdef0123456789abcdef01234567"


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"") -> None:
        self.status = status
        self._body = body

    def read(self, _size: int = -1) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class _RecordingOpener:
    def __init__(self) -> None:
        self.requests = []

    def open(self, request, timeout=0):
        self.requests.append((request, timeout))
        url = request.full_url
        if url.endswith("/api/v2/auth/login"):
            return _Response(status=204)
        if url.endswith("/api/v2/torrents/info"):
            return _Response(
                status=200,
                body=json.dumps([{"hash": TORRENT_HASH}]).encode("utf-8"),
            )
        if url.endswith(("/api/v2/torrents/stop", "/api/v2/torrents/start", "/api/v2/torrents/delete")):
            return _Response(status=200)
        raise AssertionError(f"unexpected URL: {url}")


def _load_writer(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ATLAS_DOWNLOADS_WRITER_TOKEN", TOKEN)
    monkeypatch.setenv("ATLAS_DOWNLOADS_JOB_ID_KEY", JOB_KEY)
    monkeypatch.setenv("ATLAS_QBITTORRENT_USERNAME", "test-user")
    monkeypatch.setenv("ATLAS_QBITTORRENT_PASSWORD", "test-password")
    monkeypatch.setenv("ATLAS_QBITTORRENT_BASE_URL", "http://qbit.test")
    module = importlib.import_module("atlas_api.downloads_writer")
    return importlib.reload(module)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def _job_id() -> str:
    return opaque_job_id(TORRENT_HASH, JOB_KEY)


def test_health_is_public_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_writer(monkeypatch)
    response = TestClient(module.app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_missing_and_invalid_service_tokens_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_writer(monkeypatch)
    client = TestClient(module.app)
    payload = {"job_id": _job_id(), "action": "resume"}
    assert client.post("/internal/v1/downloads/action", json=payload).status_code == 401
    assert client.post(
        "/internal/v1/downloads/action",
        headers={"Authorization": "Bearer wrong-token"},
        json=payload,
    ).status_code == 401


@pytest.mark.parametrize(
    ("action", "endpoint"),
    [
        ("stop_seeding", "/api/v2/torrents/stop"),
        ("resume", "/api/v2/torrents/start"),
        ("remove_job", "/api/v2/torrents/delete"),
    ],
)
def test_allowlisted_actions_use_expected_qbit_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    endpoint: str,
) -> None:
    module = _load_writer(monkeypatch)
    opener = _RecordingOpener()
    monkeypatch.setattr(module, "build_opener", lambda *_args: opener)

    response = TestClient(module.app).post(
        "/internal/v1/downloads/action",
        headers=_auth(),
        json={"job_id": _job_id(), "action": action},
    )
    assert response.status_code == 200

    mutation = opener.requests[-1][0]
    assert mutation.full_url.endswith(endpoint)
    payload = parse_qs(mutation.data.decode("utf-8"))
    assert payload["hashes"] == [TORRENT_HASH]
    if action == "remove_job":
        assert payload["deleteFiles"] == ["false"]
    else:
        assert "deleteFiles" not in payload


def test_destructive_unlisted_action_is_rejected_before_qbit(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_writer(monkeypatch)
    opener = _RecordingOpener()
    monkeypatch.setattr(module, "build_opener", lambda *_args: opener)
    response = TestClient(module.app).post(
        "/internal/v1/downloads/action",
        headers=_auth(),
        json={"job_id": _job_id(), "action": "delete_files"},
    )
    assert response.status_code == 400
    assert opener.requests == []


def test_unknown_opaque_job_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_writer(monkeypatch)
    opener = _RecordingOpener()
    monkeypatch.setattr(module, "build_opener", lambda *_args: opener)
    response = TestClient(module.app).post(
        "/internal/v1/downloads/action",
        headers=_auth(),
        json={
            "job_id": opaque_job_id("different-hash", JOB_KEY),
            "action": "resume",
        },
    )
    assert response.status_code == 404
