from __future__ import annotations

from urllib.error import HTTPError

import pytest

from atlas.downloads import DownloadState, DownloadsError, QBittorrentReadOnlyClient


def test_base_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="must not contain credentials"):
        QBittorrentReadOnlyClient(
            "http://user:secret@127.0.0.1:8080",
            "user",
            "secret",
        )


def test_normalize_torrent_excludes_operational_and_sensitive_fields() -> None:
    raw = {
        "name": "Ubuntu ISO",
        "category": "linux",
        "state": "downloading",
        "progress": 0.25,
        "size": 1000,
        "downloaded": 250,
        "dlspeed": 100,
        "upspeed": 10,
        "eta": 20,
        "hash": "deadbeef",
        "magnet_uri": "magnet:?xt=...",
        "tracker": "https://tracker.invalid",
        "save_path": "/downloads/private",
        "content_path": "/downloads/private/file",
        "peers": [{"ip": "203.0.113.1"}],
    }
    item = QBittorrentReadOnlyClient._normalize_torrent(raw)
    assert item.name == "Ubuntu ISO"
    assert item.category == "linux"
    assert item.state == DownloadState.DOWNLOADING
    assert item.progress == 0.25
    assert set(item.to_dict()) == {
        "name",
        "category",
        "state",
        "progress",
        "total_bytes",
        "downloaded_bytes",
        "download_rate",
        "upload_rate",
        "eta_seconds",
    }


def test_unknown_qbittorrent_state_is_bounded() -> None:
    item = QBittorrentReadOnlyClient._normalize_torrent(
        {"name": "Example", "state": "futureState"}
    )
    assert item.state == DownloadState.UNKNOWN


def test_authentication_error_never_contains_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    password = "super-secret-password"
    client = QBittorrentReadOnlyClient(
        "http://127.0.0.1:8080",
        "atlas",
        password,
    )

    def fail(*args, **kwargs):
        raise HTTPError(
            "http://127.0.0.1:8080/api/v2/auth/login",
            403,
            "Forbidden",
            {},
            None,
        )

    monkeypatch.setattr(client._opener, "open", fail)
    with pytest.raises(DownloadsError) as exc:
        client.collect()
    assert password not in str(exc.value)




def test_qbittorrent_login_accepts_204_no_content(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, limit: int = -1) -> bytes:
            return b""

    client = QBittorrentReadOnlyClient(
        "http://127.0.0.1:8080",
        "user",
        "password",
    )
    monkeypatch.setattr(client._opener, "open", lambda *args, **kwargs: Response())

    client._login()


def test_qbittorrent_login_accepts_legacy_200_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, limit: int = -1) -> bytes:
            return b"Ok."

    client = QBittorrentReadOnlyClient(
        "http://127.0.0.1:8080",
        "user",
        "password",
    )
    monkeypatch.setattr(client._opener, "open", lambda *args, **kwargs: Response())

    client._login()


def test_qbittorrent_login_rejects_legacy_200_non_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, limit: int = -1) -> bytes:
            return b"Fails."

    client = QBittorrentReadOnlyClient(
        "http://127.0.0.1:8080",
        "user",
        "password",
    )
    monkeypatch.setattr(client._opener, "open", lambda *args, **kwargs: Response())

    with pytest.raises(DownloadsError):
        client._login()


def test_pr66_stage1c_upload_state_contract() -> None:
    """Upload-side qBittorrent states must not inflate active downloads."""
    expected = {
        "uploading": DownloadState.SEEDING,
        "forcedUP": DownloadState.SEEDING,
        "stalledUP": DownloadState.SEEDING,
        "queuedUP": DownloadState.COMPLETED,
        "pausedUP": DownloadState.COMPLETED,
        "stoppedUP": DownloadState.COMPLETED,
        "checkingUP": DownloadState.CHECKING,
    }

    for raw_state, normalized_state in expected.items():
        item = QBittorrentReadOnlyClient._normalize_torrent(
            {
                "name": raw_state,
                "state": raw_state,
                "progress": 1.0,
            }
        )
        assert item.state == normalized_state


def test_pr66_stage1c_seeding_counts_as_completed_not_active() -> None:
    """A seeding torrent is download-complete even when upload remains active."""
    from atlas.downloads import DownloadItem, DownloadsSnapshot

    snapshot = DownloadsSnapshot.build(
        (
            DownloadItem(
                name="Seeder",
                category="movies",
                state=DownloadState.SEEDING,
                progress=1.0,
                total_bytes=1000,
                downloaded_bytes=1000,
                download_rate=0,
                upload_rate=50,
                eta_seconds=None,
            ),
        ),
        total_download_rate=0,
        total_upload_rate=50,
    )

    assert snapshot.summary.active == 0
    assert snapshot.summary.completed == 1
    assert snapshot.summary.total_upload_rate == 50


def test_pr66_stage1c_collection_is_bounded_and_deterministic() -> None:
    """The published item list is capped and selected deterministically."""
    client = QBittorrentReadOnlyClient(
        "http://127.0.0.1:8080",
        "user",
        "password",
    )
    client._login = lambda: None  # type: ignore[method-assign]

    names = [f"Item {index:03d}" for index in range(150)]
    torrents = [
        {
            "name": name,
            "state": "downloading",
            "progress": 0.5,
            "size": 1000,
            "downloaded": 500,
            "dlspeed": 10,
            "upspeed": 0,
            "eta": 50,
        }
        for name in reversed(names)
    ]

    def fake_json_get(path: str):
        if path == "api/v2/torrents/info":
            return torrents
        if path == "api/v2/transfer/info":
            return {"dl_info_speed": 1234, "up_info_speed": 5678}
        raise AssertionError(f"unexpected path: {path}")

    client._json_get = fake_json_get  # type: ignore[method-assign]

    snapshot = client.collect()

    assert len(snapshot.downloads) == 100
    assert [item.name for item in snapshot.downloads] == sorted(names)[:100]
    assert snapshot.summary.total_download_rate == 1234
    assert snapshot.summary.total_upload_rate == 5678

