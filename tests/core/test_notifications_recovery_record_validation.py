from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"
COMMIT = "a" * 40
IMAGE = "sha256:" + "b" * 64

NOTIFICATIONS_ROW = "|".join((
    "notifications",
    "modules/notifications/docker-compose.yml",
    "notifications",
    "atlas-notifications-worker",
    "/atlas-notifications-worker",
    "worker:test",
    IMAGE,
))


def make_archive(path: Path) -> None:
    marker = b"historical notifications source"
    with tarfile.open(path, "w:gz") as archive:
        entry = tarfile.TarInfo(
            "modules/notifications/src/formatter.py"
        )
        entry.size = len(marker)
        archive.addfile(entry, io.BytesIO(marker))


def invoke(tmp_path: Path, scenario: str):
    record = tmp_path / "baseline-test"
    record.mkdir()

    (record / "status").write_text("verified\n", encoding="utf-8")
    (record / "metadata").write_text(
        "type=baseline\n"
        "deployment_id=baseline-test\n"
        f"core_commit={COMMIT}\n"
        f"ingress_commit={COMMIT}\n"
        f"notifications_commit={COMMIT}\n"
        "sports_commit=\n",
        encoding="utf-8",
    )

    (record / "core-source.tar.gz").write_bytes(b"core fixture")
    (record / "ingress-source.tar.gz").write_bytes(
        b"ingress fixture"
    )

    make_archive(record / "notifications-source.tar.gz")

    (record / "notifications-image.tsv").write_text(
        NOTIFICATIONS_ROW + "\n", encoding="utf-8"
    )
    (record / "images.tsv").write_text(
        "core|docker-compose.yml|core|core-service|"
        f"/core-service|core:test|{IMAGE}\n"
        + NOTIFICATIONS_ROW + "\n",
        encoding="utf-8",
    )
    (record / "notifications-source-commit").write_text(
        COMMIT + "\n", encoding="utf-8"
    )

    if scenario in ("explicit-historical", "managed-mode"):
        mode = (
            "historical"
            if scenario == "explicit-historical"
            else "managed"
        )
        with (record / "metadata").open(
            "a", encoding="utf-8"
        ) as metadata:
            metadata.write(
                f"notifications_source_mode={mode}\n"
            )

    if scenario == "missing-source":
        (record / "notifications-source.tar.gz").unlink()
    elif scenario == "missing-image-evidence":
        (record / "notifications-image.tsv").unlink()
    elif scenario == "missing-provenance":
        (record / "notifications-source-commit").unlink()
    elif scenario == "mismatched-image-manifest":
        (record / "notifications-image.tsv").write_text(
            NOTIFICATIONS_ROW.replace(IMAGE, "sha256:" + "c" * 64)
            + "\n",
            encoding="utf-8",
        )
    elif scenario == "historical":
        metadata = record / "metadata"
        metadata.write_text(
            metadata.read_text(encoding="utf-8").replace(
                f"notifications_commit={COMMIT}\n",
                "notifications_commit=\n",
            ),
            encoding="utf-8",
        )
        (record / "notifications-source.tar.gz").unlink()
        (record / "notifications-image.tsv").unlink()
        (record / "notifications-source-commit").unlink()
        (record / "images.tsv").write_text(
            "core|docker-compose.yml|core|core-service|"
            f"/core-service|core:test|{IMAGE}\n",
            encoding="utf-8",
        )
    elif scenario not in (
        "complete", "explicit-historical", "managed-mode"
    ):
        raise AssertionError(f"Unexpected scenario: {scenario}")

    script = r"""
set -euo pipefail
source "$ATLAS_TEST_DEPLOYMENT"

atlas_deployment_current_id() {
  printf '%s\n' baseline-test
}

atlas_deployment_record_dir() {
  [[ "$1" == baseline-test ]] || return 1
  printf '%s\n' "$ATLAS_TEST_RECORD"
}

atlas_deployment_require_current_record
"""

    return subprocess.run(
        ["bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
            "ATLAS_TEST_RECORD": str(record),
        },
    )


def test_accepts_complete_notifications_recovery_record(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, "complete")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path / "baseline-test")


@pytest.mark.parametrize("scenario", [
    "missing-source",
    "missing-image-evidence",
    "missing-provenance",
    "mismatched-image-manifest",
])
def test_rejects_incomplete_notifications_recovery_record(
    tmp_path: Path,
    scenario: str,
) -> None:
    result = invoke(tmp_path, scenario)
    assert result.returncode != 0, (
        f"Incorrectly accepted {scenario}: {result.stdout}"
    )


def test_accepts_historical_record_without_notifications_adoption(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, "historical")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(tmp_path / "baseline-test")


def test_current_record_accepts_explicit_historical_source_mode(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, "explicit-historical")
    assert result.returncode == 0, result.stderr


def test_current_record_rejects_unsupported_managed_source_mode(
    tmp_path: Path,
) -> None:
    result = invoke(tmp_path, "managed-mode")
    assert result.returncode != 0
    assert "unsupported Notifications source mode" in result.stderr
