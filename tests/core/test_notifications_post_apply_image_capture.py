from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"

COMMIT = "a" * 40
CORE_IMAGE = "sha256:" + "b" * 64
INGRESS_IMAGE = "sha256:" + "c" * 64
NOTIFICATIONS_IMAGE = "sha256:" + "d" * 64

NOTIFICATIONS_ROW = (
    "notifications|modules/notifications/docker-compose.yml|"
    "notifications|atlas-notifications-worker|"
    "/atlas-notifications-worker|worker:test|"
    + NOTIFICATIONS_IMAGE
)


def invoke(tmp_path: Path, adopted: bool, image_drift: bool = False):
    project = tmp_path / "project"
    project.mkdir()
    (project / "stack").mkdir()

    (project / ".env").write_text("", encoding="utf-8")
    (project / "docker-compose.yml").write_text(
        "services: {}\n", encoding="utf-8"
    )
    (project / "stack/ingress.yml").write_text(
        "services: {}\n", encoding="utf-8"
    )

    record = tmp_path / "record"
    record.mkdir()

    (record / "metadata").write_text(
        "type=update\n"
        "deployment_id=test-update\n"
        "sports_commit=\n"
        + (f"notifications_commit={COMMIT}\n" if adopted else ""),
        encoding="utf-8",
    )

    if adopted:
        (record / "notifications-source.tar.gz").write_bytes(
            b"historical-notifications-source"
        )
        (record / "notifications-image.tsv").write_text(
            NOTIFICATIONS_ROW + "\n", encoding="utf-8"
        )
        (record / "notifications-source-commit").write_text(
            COMMIT + "\n", encoding="utf-8"
        )

    script = r"""
set -euo pipefail

source "$ATLAS_TEST_DEPLOYMENT"

# Docker is intercepted entirely in this subprocess; no executable
# named docker is invoked, and no production container is inspected.
docker() {
  if [[ "${1:-}" == compose ]]; then
    if [[ " $* " == *'stack/ingress.yml'* ]]; then
      printf '%s\n' ingress-test-id
    elif [[ " $* " == *'docker-compose.yml'* ]]; then
      printf '%s\n' core-test-id
    else
      return 91
    fi
    return 0
  fi

  if [[ "${1:-}" == inspect ]]; then
    case "${@: -1}" in
      core-test-id)
        printf '%s\n' \
          "core|core-service|/core-service|core:test|$ATLAS_TEST_CORE_IMAGE"
        ;;
      ingress-test-id)
        printf '%s\n' \
          "ingress|ingress-service|/ingress-service|ingress:test|$ATLAS_TEST_INGRESS_IMAGE"
        ;;
      atlas-notifications-worker)
        printf '%s\n' "$ATLAS_TEST_WORKER_IMAGE"
        ;;
      *)
        return 92
        ;;
    esac
    return 0
  fi

  return 93
}

atlas_deployment_capture_images "$ATLAS_TEST_RECORD"
"""

    env = {
        **os.environ,
        "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        "ATLAS_TEST_RECORD": str(record),
        "ATLAS_PROJECT_DIR": str(project),
        "ATLAS_TEST_CORE_IMAGE": CORE_IMAGE,
        "ATLAS_TEST_INGRESS_IMAGE": INGRESS_IMAGE,
        "ATLAS_TEST_WORKER_IMAGE": (
            "sha256:" + "e" * 64
            if image_drift else NOTIFICATIONS_IMAGE
        ),
    }

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    manifest = record / "images.tsv"
    rows = (
        manifest.read_text(encoding="utf-8").splitlines()
        if manifest.is_file()
        else []
    )

    return result, rows


def test_historical_image_capture_still_records_core_and_ingress(
    tmp_path: Path,
) -> None:
    result, rows = invoke(tmp_path, adopted=False)

    assert result.returncode == 0, result.stderr
    assert len(rows) == 2
    assert rows[0].startswith(
        "core|docker-compose.yml|core|core-service|"
    )
    assert rows[1].startswith(
        "ingress|stack/ingress.yml|ingress|ingress-service|"
    )
    assert not any(
        row.startswith("notifications|") for row in rows
    )


def test_adopted_image_capture_retains_notifications_worker(
    tmp_path: Path,
) -> None:
    result, rows = invoke(tmp_path, adopted=True)

    assert result.returncode == 0, result.stderr
    assert len(rows) == 3
    assert rows[2] == NOTIFICATIONS_ROW


def test_changed_notifications_image_is_rejected_without_publishing_manifest(
    tmp_path: Path,
) -> None:
    result, rows = invoke(
        tmp_path, adopted=True, image_drift=True
    )

    assert result.returncode != 0
    assert "Notifications worker image differs" in result.stderr
    assert rows == []
    assert not (tmp_path / "record/images.tsv").exists()
