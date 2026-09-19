from __future__ import annotations

from pathlib import Path
import subprocess
import tarfile

import importlib.util

_worker_test = Path(__file__).with_name(
    "test_notifications_worker_attestation.py"
)
_spec = importlib.util.spec_from_file_location(
    "atlas_notifications_worker_test_fixture", _worker_test
)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

IMAGE_ID = _module.IMAGE_ID
attest = _module.attest
container_details = _module.container_details
setup_case = _module.setup_case



PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts/commands/deployment.sh"
HELPER = "atlas_deployment_capture_notifications_adoption_evidence"


def capture(
    checkout: Path,
    commit: str,
    record: Path,
    bin_dir: Path,
    details: dict,
) -> subprocess.CompletedProcess[str]:
    # Keep the simulated worker inspection identical to the attestation test.
    inspection = bin_dir.parent / "inspect.json"
    import json
    import os

    inspection.write_text(json.dumps([details]), encoding="utf-8")
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        "ATLAS_TEST_DOCKER_INSPECT": str(inspection),
    }
    return subprocess.run(
        [
            "bash", "-c",
            'set -euo pipefail; '
            'source "$ATLAS_TEST_DEPLOYMENT"; '
            f'{HELPER} "$1" "$2" "$3"',
            "adoption-test",
            str(record), str(checkout), commit,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_captures_matching_source_and_image_evidence(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    record = tmp_path / "recovery-evidence"
    record.mkdir()
    details = container_details(checkout)

    # The existing attestation must be successful before evidence capture.
    assert attest(checkout, commit, bin_dir, details).returncode == 0

    result = capture(checkout, commit, record, bin_dir, details)
    assert result.returncode == 0, result.stderr

    archive = record / "notifications-source.tar.gz"
    manifest = record / "notifications-image.tsv"
    provenance = record / "notifications-source-commit"

    assert archive.is_file()
    assert manifest.is_file()
    assert provenance.read_text(encoding="utf-8").strip() == commit

    with tarfile.open(archive, "r:gz") as contents:
        member = contents.extractfile(
            "modules/notifications/scripts/worker.sh"
        )
        assert member is not None
        assert member.read() == b"#!/usr/bin/env bash\nexit 0\n"

    fields = manifest.read_text(encoding="utf-8").strip().split("|")
    assert len(fields) == 7
    assert fields[:4] == [
        "notifications",
        "modules/notifications/docker-compose.yml",
        "notifications",
        "atlas-notifications-worker",
    ]
    assert fields[-1] == IMAGE_ID


def test_rejects_wrong_live_mount_without_publishing_evidence(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    record = tmp_path / "recovery-evidence"
    record.mkdir()
    details = container_details(checkout)
    details["Mounts"][0]["Source"] = str(tmp_path / "wrong-source")

    result = capture(checkout, commit, record, bin_dir, details)

    assert result.returncode != 0
    assert list(record.iterdir()) == []


def test_rejects_existing_evidence_without_overwriting(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    record = tmp_path / "recovery-evidence"
    record.mkdir()
    existing = record / "notifications-image.tsv"
    existing.write_text("preserve-existing\n", encoding="utf-8")

    result = capture(
        checkout, commit, record, bin_dir, container_details(checkout)
    )

    assert result.returncode != 0
    assert existing.read_text(encoding="utf-8") == "preserve-existing\n"
    assert not (record / "notifications-source.tar.gz").exists()
