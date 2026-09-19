from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"

COMMIT = "c" * 40
CORE_IMAGE = "sha256:" + "a" * 64
WORKER_IMAGE = "sha256:" + "d" * 64
DRIFT_IMAGE = "sha256:" + "e" * 64

CORE_ROW = (
    "core|docker-compose.yml|atlas|api|/atlas-api|"
    "atlas-api:test|" + CORE_IMAGE
)

WORKER_ROW = (
    "notifications|modules/notifications/docker-compose.yml|"
    "notifications|atlas-notifications-worker|"
    "/atlas-notifications-worker|notifications:test|" + WORKER_IMAGE
)


def run_verifier(
    tmp_path: Path,
    *,
    mode: str = "matching",
    adopted: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    deployment_root = tmp_path / "deployments"
    records = deployment_root / "records"
    records.mkdir(parents=True)

    baseline = records / "baseline-test"
    transaction = records / "update-test"

    baseline.mkdir()
    transaction.mkdir()

    metadata = [
        "type=baseline",
        "deployment_id=baseline-test",
    ]

    if adopted:
        metadata.append(f"notifications_commit={COMMIT}")

    (baseline / "metadata").write_text(
        "\n".join(metadata) + "\n",
        encoding="utf-8",
    )
    (baseline / "status").write_text(
        "verified\n", encoding="utf-8"
    )

    (transaction / "metadata").write_text(
        "type=update\n"
        "deployment_id=update-test\n"
        "previous_baseline=baseline-test\n",
        encoding="utf-8",
    )

    rows = [CORE_ROW]

    if adopted:
        rows.append(WORKER_ROW)

        (
            baseline / "notifications-source.tar.gz"
        ).write_bytes(
            b"recorded-notifications-source\n"
        )

        (
            baseline / "notifications-image.tsv"
        ).write_text(
            WORKER_ROW + "\n",
            encoding="utf-8",
        )

        (
            baseline / "notifications-source-commit"
        ).write_text(
            COMMIT + "\n",
            encoding="utf-8",
        )

    (baseline / "images.tsv").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    live_row = WORKER_ROW
    actual_worker_image = WORKER_IMAGE

    if mode == "source-attestation-fails":
        pass
    elif mode == "worker-row-drift":
        live_row = WORKER_ROW.replace(
            WORKER_IMAGE, DRIFT_IMAGE
        )
    elif mode == "container-image-drift":
        actual_worker_image = DRIFT_IMAGE
    elif mode == "missing-source-evidence" and adopted:
        (
            baseline / "notifications-source.tar.gz"
        ).unlink()
    elif mode == "wrong-recorded-image" and adopted:
        (
            baseline / "notifications-image.tsv"
        ).write_text(
            WORKER_ROW.replace(
                WORKER_IMAGE, DRIFT_IMAGE
            ) + "\n",
            encoding="utf-8",
        )
    elif mode == "invalid-commit" and adopted:
        (baseline / "metadata").write_text(
            "type=baseline\n"
            "deployment_id=baseline-test\n"
            "notifications_commit=invalid\n",
            encoding="utf-8",
        )
    elif mode != "matching":
        raise AssertionError(
            f"unsupported fixture mode: {mode}"
        )

    # Source the real deployment code but replace every external
    # verification boundary. No real Docker or worker inspection.
    script = r'''
set -euo pipefail

source "$DEPLOYMENT_FILE"

atlas_command_doctor() {
  printf 'doctor\n' >> "$EVENT_LOG"
}

atlas_command_verify() {
  printf 'atlas-verify\n' >> "$EVENT_LOG"
}

docker() {
  [[ "$#" -eq 4 &&
    "$1" == inspect &&
    "$2" == --format &&
    "$3" == '{{.Image}}' ]] || return 1

  case "$4" in
    /atlas-api)
      printf '%s\n' "$EXPECTED_CORE_IMAGE"
      ;;
    /atlas-notifications-worker)
      printf '%s\n' "$ACTUAL_WORKER_IMAGE"
      ;;
    *)
      return 1
      ;;
  esac
}

atlas_deployment_notifications_live_worker_row() {
  [[ "$#" -eq 2 &&
    "$1" == /opt/project-atlas &&
    "$2" == "$EXPECTED_COMMIT" ]] || return 1

  printf 'worker-attestation\n' >> "$EVENT_LOG"

  if [[ "$MODE" == source-attestation-fails ]]; then
    return 1
  fi

  printf '%s\n' "$LIVE_WORKER_ROW"
}

atlas_deployment_verify_rollback_runtime \
  "$TRANSACTION_RECORD" core
'''

    log = tmp_path / "events.log"

    env = os.environ.copy()
    env.update(
        {
            "ATLAS_DEPLOYMENT_DIR": str(
                deployment_root
            ),
            "ATLAS_RUNTIME_CONFIG_DIR": str(
                tmp_path / "runtime-config"
            ),
            "ATLAS_PROJECT_DIR": str(ROOT),
            "DEPLOYMENT_FILE": str(DEPLOYMENT),
            "TRANSACTION_RECORD": str(transaction),
            "EXPECTED_COMMIT": COMMIT,
            "EXPECTED_CORE_IMAGE": CORE_IMAGE,
            "ACTUAL_WORKER_IMAGE": actual_worker_image,
            "LIVE_WORKER_ROW": live_row,
            "MODE": mode,
            "EVENT_LOG": str(log),
        }
    )

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    result.events = (
        log.read_text(encoding="utf-8")
        if log.exists()
        else ""
    )

    return result, baseline, transaction


def assert_verification_failed(
    result: subprocess.CompletedProcess[str],
    baseline: Path,
    transaction: Path,
) -> None:
    assert result.returncode != 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert (
        baseline / "status"
    ).read_text(encoding="utf-8") == "verified\n"

    assert (
        transaction / "metadata"
    ).read_text(encoding="utf-8").endswith(
        "previous_baseline=baseline-test\n"
    )

    assert "doctor\n" in result.events
    assert "atlas-verify\n" in result.events


def test_historical_baseline_does_not_require_notifications_attestation(
    tmp_path: Path,
) -> None:
    result, _, _ = run_verifier(
        tmp_path,
        adopted=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.events == "doctor\natlas-verify\n"


def test_adopted_baseline_requires_matching_attestation(
    tmp_path: Path,
) -> None:
    result, _, _ = run_verifier(tmp_path)

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert result.events == (
        "doctor\n"
        "atlas-verify\n"
        "worker-attestation\n"
    )


@pytest.mark.parametrize(
    "mode",
    (
        "source-attestation-fails",
        "worker-row-drift",
        "container-image-drift",
        "missing-source-evidence",
        "wrong-recorded-image",
        "invalid-commit",
    ),
)
def test_adopted_baseline_rejects_attestation_or_evidence_drift(
    tmp_path: Path,
    mode: str,
) -> None:
    result, baseline, transaction = run_verifier(
        tmp_path,
        mode=mode,
    )

    assert_verification_failed(
        result, baseline, transaction
    )
