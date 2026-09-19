from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"
COMMIT = "a" * 40
IMAGE = "sha256:" + "b" * 64
ROW = (
    "notifications|modules/notifications/docker-compose.yml|"
    "notifications|atlas-notifications-worker|"
    f"/atlas-notifications-worker|worker:test|{IMAGE}"
)


def invoke(tmp_path: Path, adopted: bool):
    previous = tmp_path / "previous"
    previous.mkdir()

    (previous / "metadata").write_text(
        "type=baseline\n"
        "deployment_id=previous\n"
        f"core_commit={COMMIT}\n"
        f"ingress_commit={COMMIT}\n"
        "sports_commit=\n"
        + (f"notifications_commit={COMMIT}\n" if adopted else ""),
        encoding="utf-8",
    )

    for name in ("core-source.tar.gz", "ingress-source.tar.gz"):
        (previous / name).write_bytes(name.encode())

    previous_manifest = (
        "core|docker-compose.yml|core|core-service|"
        f"/core-service|core:test|{IMAGE}\n"
        + (ROW + "\n" if adopted else "")
    )
    (previous / "images.tsv").write_text(
        previous_manifest, encoding="utf-8"
    )

    evidence = (
        "notifications-source.tar.gz",
        "notifications-image.tsv",
        "notifications-source-commit",
    )
    if adopted:
        (previous / evidence[0]).write_bytes(b"historical-source")
        (previous / evidence[1]).write_text(
            ROW + "\n", encoding="utf-8"
        )
        (previous / evidence[2]).write_text(
            COMMIT + "\n", encoding="utf-8"
        )

    script = r"""
set -euo pipefail
source "$ATLAS_TEST_DEPLOYMENT"

atlas_deployment_record_dir() {
  [[ "$1" == update-test ]] || return 1
  printf '%s\n' "$ATLAS_TEST_UPDATE"
}

atlas_deployment_preserve_rollback_images() {
  [[ "$1" == "$ATLAS_TEST_PREVIOUS" ]] || return 1
  [[ "$2" == "$ATLAS_TEST_UPDATE" ]] || return 1
  printf '%s\n' preserved > "$2/rollback-images.tsv"
}

atlas_deployment_archive_source() {
  [[ "$1" =~ ^[0-9a-f]{40}$ ]] || return 1
  printf '%s\n' new-core-source > "$2"
}

atlas_deployment_set_status() {
  printf '%s\n' "$2" > "$1/status"
}

atlas_deployment_prepare_update \
  update-test core "$ATLAS_TEST_PREVIOUS"
"""

    record = tmp_path / "update-test"
    result = subprocess.run(
        ["bash", "-c", script],
        env={
            **os.environ,
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
            "ATLAS_TEST_PREVIOUS": str(previous),
            "ATLAS_TEST_UPDATE": str(record),
            "ATLAS_PROJECT_DIR": str(ROOT),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, previous, record, evidence, previous_manifest


def test_historical_core_update_preparation_still_works(
    tmp_path: Path,
) -> None:
    result, _, record, _, previous_manifest = invoke(
        tmp_path, adopted=False
    )
    assert result.returncode == 0, result.stderr
    assert (record / "status").read_text().strip() == "prepared"
    assert (record / "pre-images.tsv").read_text() == previous_manifest
    assert (record / "core-source.tar.gz").is_file()


def test_adopted_notifications_evidence_survives_core_update_preparation(
    tmp_path: Path,
) -> None:
    result, previous, record, evidence, previous_manifest = invoke(
        tmp_path, adopted=True
    )
    assert result.returncode == 0, result.stderr

    assert (
        f"notifications_commit={COMMIT}\n"
        in (record / "metadata").read_text(encoding="utf-8")
    )
    for name in evidence:
        assert (record / name).read_bytes() == (
            previous / name
        ).read_bytes(), name

    assert (record / "pre-images.tsv").read_text() == previous_manifest
    assert (record / "status").read_text().strip() == "prepared"
