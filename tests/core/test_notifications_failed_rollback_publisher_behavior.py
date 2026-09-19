from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"

COMMIT = "c" * 40
IMAGE = "sha256:" + "d" * 64
DRIFT_IMAGE = "sha256:" + "e" * 64

ROW = (
    "notifications|modules/notifications/docker-compose.yml|"
    "notifications|atlas-notifications-worker|"
    "/atlas-notifications-worker|notifications:test|" + IMAGE
)

CORE_ROW = (
    "core|docker-compose.yml|atlas|api|/atlas-api|"
    "atlas-api:test|sha256:" + "a" * 64
)

ARCHIVE = b"previous-baseline-notifications-source\n"

EVIDENCE = (
    "notifications-source.tar.gz",
    "notifications-image.tsv",
    "notifications-source-commit",
)


def run_publisher(
    tmp_path: Path,
    *,
    mode: str = "matching",
    adopted: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    root = tmp_path / "deployments"
    records = root / "records"
    records.mkdir(parents=True)

    previous = records / "baseline-test"
    failed = records / "update-test"
    published = records / "baseline-reconciliation-test"

    previous.mkdir()
    failed.mkdir()

    metadata = [
        "type=baseline",
        "deployment_id=baseline-test",
        "source_commit=" + "a" * 40,
        "core_commit=" + "a" * 40,
        "ingress_commit=" + "a" * 40,
        "scope=all",
        "migration=none",
    ]

    if adopted:
        metadata.append(f"notifications_commit={COMMIT}")

    (previous / "metadata").write_text(
        "\n".join(metadata) + "\n",
        encoding="utf-8",
    )
    (previous / "status").write_text(
        "verified\n", encoding="utf-8"
    )
    (previous / "core-source.tar.gz").write_bytes(
        b"previous-core-source\n"
    )
    (previous / "ingress-source.tar.gz").write_bytes(
        b"previous-ingress-source\n"
    )
    (failed / "status").write_text(
        "failed\n", encoding="utf-8"
    )

    rows = [CORE_ROW]
    if adopted:
        rows.append(ROW)
        (previous / EVIDENCE[0]).write_bytes(ARCHIVE)
        (previous / EVIDENCE[1]).write_text(
            ROW + "\n", encoding="utf-8"
        )
        (previous / EVIDENCE[2]).write_text(
            COMMIT + "\n", encoding="utf-8"
        )

    (previous / "images.tsv").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    live_row = ROW

    if mode == "missing-archive" and adopted:
        (previous / EVIDENCE[0]).unlink()
    elif mode == "wrong-commit" and adopted:
        (previous / EVIDENCE[2]).write_text(
            "e" * 40 + "\n", encoding="utf-8"
        )
    elif mode == "wrong-image-evidence" and adopted:
        (previous / EVIDENCE[1]).write_text(
            ROW.replace(IMAGE, DRIFT_IMAGE) + "\n",
            encoding="utf-8",
        )
    elif mode == "missing-manifest-row" and adopted:
        (previous / "images.tsv").write_text(
            CORE_ROW + "\n", encoding="utf-8"
        )
    elif mode == "capture-image-drift" and adopted:
        live_row = ROW.replace(IMAGE, DRIFT_IMAGE)
    elif mode != "matching":
        raise AssertionError(f"invalid fixture mode: {mode}")

    # Only the reconciliation publisher is real. Both runtime
    # functions operate on pytest records, never on production.
    script = r'''
set -euo pipefail

source "$DEPLOYMENT_FILE"

atlas_deployment_new_id() {
  test "$1" = baseline-reconciliation
  printf '%s\n' baseline-reconciliation-test
}

atlas_deployment_capture_images() {
  local record="$1"

  grep -v '^notifications|' \
    "$PREVIOUS_RECORD/images.tsv" > "$record/images.tsv"

  if [[ "$ADOPTED" == true ]]; then
    printf '%s\n' "$LIVE_ROW" >> "$record/images.tsv"
  fi
}

atlas_deployment_verify_runtime() {
  local record="$1"

  test -s "$record/images.tsv" || return 1

  if [[ "$ADOPTED" == true ]]; then
    test "$(
      grep -c '^notifications|' "$record/images.tsv"
    )" -eq 1 || return 1

    grep -Fqx -- "$EXPECTED_ROW" \
      "$record/notifications-image.tsv" || return 1

    grep -Fqx -- "$EXPECTED_ROW" \
      "$record/images.tsv" || return 1

    grep -Fxq \
      "notifications_commit=$EXPECTED_COMMIT" \
      "$record/metadata" || return 1

    test "$(
      cat "$record/notifications-source-commit"
    )" = "$EXPECTED_COMMIT" || return 1
  fi
}

atlas_deployment_publish_reconciliation_baseline \
  update-test \
  "$FAILED_RECORD" \
  baseline-test \
  "$PREVIOUS_RECORD" \
  core
'''

    env = os.environ.copy()
    env.update(
        {
            "ATLAS_DEPLOYMENT_DIR": str(root),
            "ATLAS_RUNTIME_CONFIG_DIR": str(
                tmp_path / "runtime-config"
            ),
            "ATLAS_PROJECT_DIR": str(ROOT),
            "DEPLOYMENT_FILE": str(DEPLOYMENT),
            "PREVIOUS_RECORD": str(previous),
            "FAILED_RECORD": str(failed),
            "EXPECTED_ROW": ROW,
            "EXPECTED_COMMIT": COMMIT,
            "LIVE_ROW": live_row,
            "ADOPTED": "true" if adopted else "false",
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

    return result, previous, published


def assert_no_publication(
    result: subprocess.CompletedProcess[str],
    previous: Path,
    published: Path,
) -> None:
    assert result.returncode != 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not published.exists()

    assert (
        previous / "status"
    ).read_text(encoding="utf-8") == "verified\n"

    assert (
        previous.parent / "update-test" / "status"
    ).read_text(encoding="utf-8") == "failed\n"

    assert list(
        published.parent.glob(
            ".baseline-reconciliation-test.*"
        )
    ) == []


def test_adopted_publisher_preserves_exact_previous_evidence(
    tmp_path: Path,
) -> None:
    result, previous, published = run_publisher(tmp_path)

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    assert result.stdout.strip() == published.name
    assert published.is_dir()

    assert (
        published / "status"
    ).read_text(encoding="utf-8") == "verified\n"

    for name in EVIDENCE:
        assert (
            published / name
        ).read_bytes() == (
            previous / name
        ).read_bytes()

    for name in ("metadata", "provenance"):
        assert (
            f"notifications_commit={COMMIT}\n"
            in (published / name).read_text(
                encoding="utf-8"
            )
        )

    assert (
        published / "images.tsv"
    ).read_text(encoding="utf-8").splitlines().count(
        ROW
    ) == 1

    manifest = (
        published / "MANIFEST.sha256"
    ).read_text(encoding="utf-8")

    for name in EVIDENCE:
        assert name in manifest

    check = subprocess.run(
        ["sha256sum", "-c", "MANIFEST.sha256"],
        cwd=published,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr

    assert (
        previous / "status"
    ).read_text(encoding="utf-8") == "verified\n"


@pytest.mark.parametrize(
    "mode",
    (
        "missing-archive",
        "wrong-commit",
        "wrong-image-evidence",
        "missing-manifest-row",
        "capture-image-drift",
    ),
)
def test_adopted_publisher_rejects_evidence_or_image_drift(
    tmp_path: Path,
    mode: str,
) -> None:
    result, previous, published = run_publisher(
        tmp_path,
        mode=mode,
    )
    assert_no_publication(result, previous, published)


def test_historical_publisher_remains_compatible(
    tmp_path: Path,
) -> None:
    result, _, published = run_publisher(
        tmp_path,
        adopted=False,
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert published.is_dir()

    assert (
        "notifications_commit=\n"
        in (published / "metadata").read_text(
            encoding="utf-8"
        )
    )

    for name in EVIDENCE:
        assert not (published / name).exists()

    check = subprocess.run(
        ["sha256sum", "-c", "MANIFEST.sha256"],
        cwd=published,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr
