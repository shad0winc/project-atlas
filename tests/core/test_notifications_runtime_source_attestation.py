from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"

COMMIT = "a" * 40
IMAGE = "sha256:" + "b" * 64

CORE_ROW = (
    "core|docker-compose.yml|core|core-service|"
    f"/core-service|core:test|{IMAGE}"
)
WORKER_ROW = (
    "notifications|modules/notifications/docker-compose.yml|"
    "notifications|atlas-notifications-worker|"
    f"/atlas-notifications-worker|worker:test|{IMAGE}"
)


def invoke(
    tmp_path: Path,
    *,
    adopted: bool,
    mode: str = "match",
):
    record = tmp_path / "record"
    record.mkdir()

    (record / "metadata").write_text(
        "type=baseline\n"
        "deployment_id=test\n"
        + (f"notifications_commit={COMMIT}\n" if adopted else ""),
        encoding="utf-8",
    )

    (record / "images.tsv").write_text(
        CORE_ROW + "\n"
        + (WORKER_ROW + "\n" if adopted else ""),
        encoding="utf-8",
    )

    if adopted:
        (record / "notifications-source.tar.gz").write_bytes(
            b"isolated-test-source"
        )
        (record / "notifications-source-commit").write_text(
            COMMIT + "\n", encoding="utf-8"
        )
        (record / "notifications-image.tsv").write_text(
            WORKER_ROW + "\n", encoding="utf-8"
        )

    script = r"""
set -euo pipefail
source "$ATLAS_TEST_DEPLOYMENT"

# The real Docker executable is never called.
docker() {
  [[ "${1:-}" == inspect ]] || return 91
  [[ "${2:-}" == --format ]] || return 92

  case "${@: -1}" in
    /core-service|/atlas-notifications-worker)
      printf '%s\n' "$ATLAS_TEST_IMAGE"
      ;;
    *)
      return 93
      ;;
  esac
}

# This mock stands in for the separately tested checkout/mount/health
# attestation helper. The runtime verifier must call it with the
# currently verified adoption checkout and source commit.
atlas_deployment_notifications_live_worker_row() {
  [[ "$1" == /opt/project-atlas ]] || return 94
  [[ "$2" == "$ATLAS_TEST_COMMIT" ]] || return 95

  case "$ATLAS_TEST_ATTEST_MODE" in
    match)
      printf '%s\n' "$ATLAS_TEST_WORKER_ROW"
      ;;
    source-drift)
      echo 'ERROR: live Notifications source checkout is dirty.' >&2
      return 96
      ;;
    row-drift)
      printf '%s\n' "${ATLAS_TEST_WORKER_ROW/worker:test/worker:other}"
      ;;
    *)
      return 97
      ;;
  esac
}

atlas_deployment_verify_runtime "$ATLAS_TEST_RECORD"
"""

    result = subprocess.run(
        ["bash", "-c", script],
        env={
            **os.environ,
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
            "ATLAS_TEST_RECORD": str(record),
            "ATLAS_TEST_IMAGE": IMAGE,
            "ATLAS_TEST_COMMIT": COMMIT,
            "ATLAS_TEST_WORKER_ROW": WORKER_ROW,
            "ATLAS_TEST_ATTEST_MODE": mode,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result


def test_historical_runtime_verification_remains_compatible(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, adopted=False)
    assert result.returncode == 0, result.stderr


def test_adopted_runtime_verification_accepts_matching_attestation(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, adopted=True, mode="match")
    assert result.returncode == 0, result.stderr


def test_adopted_runtime_verification_rejects_source_drift(
    tmp_path: Path,
) -> None:
    result = invoke(
        tmp_path, adopted=True, mode="source-drift"
    )
    assert result.returncode != 0


def test_adopted_runtime_verification_rejects_worker_row_drift(
    tmp_path: Path,
) -> None:
    result = invoke(
        tmp_path, adopted=True, mode="row-drift"
    )
    assert result.returncode != 0
