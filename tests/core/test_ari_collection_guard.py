"""The ARI collector must preserve published state on provider failure."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE = (PROJECT_ROOT / "scripts" / "atlas-ari.sh").read_text()
COLLECTION = SOURCE.split("jellyfin_json_request() {\n", 1)[1].split(
    "\n###############################################################################\n# Forecast", 1
)[0]
COLLECTION = "jellyfin_json_request() {\n" + COLLECTION


def _collect(tmp_path: Path, mode: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    directory = tmp_path / "ari"
    history = directory / "snapshots"
    runtime = tmp_path / "runtime.json"
    media = tmp_path / "media"
    directory.mkdir()
    history.mkdir()
    media.mkdir()
    for name in ("Movies", "TV", "Anime Movies", "Anime TV"):
        (media / name).mkdir()
    latest = directory / "latest.json"
    latest.write_text('{"sentinel":true}\n')
    runtime.write_text('{"sentinel":true}\n')

    script = (
        "set -euo pipefail\n"
        + COLLECTION
        + "\n"
        + r'''
curl() {
  local url="${*: -1}"
  case "$url" in
    */System/Info) printf '%s' '{"ServerName":"Test","Version":"1.0","Id":"id"}' ;;
    */Library/VirtualFolders)
      if [[ "$MOCK_MODE" == empty_libraries ]]; then
        return 0
      fi
      if [[ "$MOCK_MODE" == invalid_library ]]; then
        printf '%s' '[{"Name":"Missing fields"}]'
        return 0
      fi
      printf '%s' '[]'
      ;;
    */Users) printf '%s' '[]' ;;
    */Items/Counts) printf '%s' '{"MovieCount":0,"ItemCount":0}' ;;
    *) return 1 ;;
  esac
}
publish_api_runtime_snapshot() { cp -- "$1" "$ARI_API_RUNTIME_FILE"; }
ari_publish_event() { :; }
ari_publish_storage_transition() { :; }
ari_publish_health_transition() { :; }
ari_calculate_health_score() { printf '100'; }
ari_health_status() { printf 'Healthy'; }
collect
'''
    )
    environment = os.environ.copy()
    environment.update({
        "ARI_DATA_DIR": str(directory),
        "ARI_SNAPSHOT_DIR": str(history),
        "LATEST_FILE": str(latest),
        "ARI_API_RUNTIME_FILE": str(runtime),
        "MEDIA_ROOT": str(media),
        "ATLAS_PROJECT_DIR": str(PROJECT_ROOT),
        "ATLAS_JELLYFIN_URL": "http://fixture.invalid",
        "ATLAS_JELLYFIN_API_KEY": "fixture",
        "MOCK_MODE": mode,
    })
    result = subprocess.run(
        ["bash", "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, directory


def test_empty_jellyfin_response_preserves_published_state(tmp_path: Path) -> None:
    result, directory = _collect(tmp_path, "empty_libraries")
    assert result.returncode != 0
    assert "ARI Jellyfin response invalid" in result.stderr
    assert (directory / "latest.json").read_text() == '{"sentinel":true}\n'
    assert (tmp_path / "runtime.json").read_text() == '{"sentinel":true}\n'
    assert list((directory / "snapshots").iterdir()) == []


def test_complete_jellyfin_response_publishes_valid_report(tmp_path: Path) -> None:
    result, directory = _collect(tmp_path, "valid")
    assert result.returncode == 0, result.stderr
    latest = json.loads((directory / "latest.json").read_text())
    assert latest["jellyfin"]["server_name"] == "Test"
    assert json.loads((tmp_path / "runtime.json").read_text()) == latest
    snapshots = list((directory / "snapshots").glob("*.json"))
    assert len(snapshots) == 1
    assert json.loads(snapshots[0].read_text()) == latest


def test_semantically_invalid_report_never_replaces_latest(tmp_path: Path) -> None:
    result, directory = _collect(tmp_path, "invalid_library")
    assert result.returncode != 0
    assert "ARI snapshot validation failed" in result.stderr
    assert (directory / "latest.json").read_text() == '{"sentinel":true}\n'
    assert (tmp_path / "runtime.json").read_text() == '{"sentinel":true}\n'
    assert list((directory / "snapshots").iterdir()) == []
