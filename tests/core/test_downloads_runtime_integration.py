"""Ingress boundary tests for the bounded Downloads runtime snapshot."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INGRESS = ROOT / "stack" / "ingress.yml"
RUNTIME_DIR = "/mnt/storage/configs/atlas/runtime/downloads"
SNAPSHOT = f"{RUNTIME_DIR}/latest.json"


def _api_service_block() -> str:
    content = INGRESS.read_text()
    start = content.index("  api:\n")
    end = content.index("\n  identity-writer:\n", start)
    return content[start:end]


def test_api_mounts_only_downloads_runtime_directory_read_only() -> None:
    api = _api_service_block()

    expected = f"{RUNTIME_DIR}:{RUNTIME_DIR}:ro"
    assert expected in api
    assert f"{RUNTIME_DIR}:{RUNTIME_DIR}:rw" not in api
    assert "/mnt/storage/configs/atlas/runtime:/mnt/storage/configs/atlas/runtime" not in api


def test_api_uses_canonical_downloads_snapshot_path() -> None:
    api = _api_service_block()

    assert f'ATLAS_DOWNLOADS_SNAPSHOT_PATH: "{SNAPSHOT}"' in api


def test_api_does_not_receive_qbittorrent_credentials() -> None:
    api = _api_service_block()

    assert "ATLAS_QBITTORRENT_USERNAME" not in api
    assert "ATLAS_QBITTORRENT_PASSWORD" not in api
