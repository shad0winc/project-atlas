"""Shell-level regression tests for the root Atlas Doctor command."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_SCRIPT = (
    PROJECT_ROOT
    / "scripts"
    / "commands"
    / "doctor.sh"
)


def run_doctor(
    *,
    health_status: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Source Doctor with a deterministic health-engine boundary."""

    harness = r"""
    set -u

    source "$ATLAS_TEST_DOCTOR_SCRIPT"

    atlas_health_python() {
      printf '%s\n' "$*" > "$ATLAS_TEST_CAPTURE_PATH"
      printf '%s\n' "${ATLAS_TEST_HEALTH_OUTPUT:-}"
      return "${ATLAS_TEST_HEALTH_STATUS:-0}"
    }

    atlas_command_doctor
    """

    environment = os.environ.copy()
    capture_path = PROJECT_ROOT / ".doctor-test-capture.tmp"

    environment.update(
        {
            "ATLAS_TEST_DOCTOR_SCRIPT": str(DOCTOR_SCRIPT),
            "ATLAS_TEST_CAPTURE_PATH": str(capture_path),
            "ATLAS_TEST_HEALTH_STATUS": str(health_status),
            "ATLAS_TEST_HEALTH_OUTPUT": (
                "Atlas Health Diagnostics\n"
                "Overall Status: HEALTHY"
            ),
        }
    )

    try:
        result = subprocess.run(
            [
                "bash",
                "-c",
                textwrap.dedent(harness),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        captured_arguments = capture_path.read_text(
            encoding="utf-8",
        )

        return subprocess.CompletedProcess(
            args=result.args,
            returncode=result.returncode,
            stdout=(
                result.stdout
                + "\nCAPTURED_ARGUMENTS="
                + captured_arguments
            ),
            stderr=result.stderr,
        )
    finally:
        capture_path.unlink(
            missing_ok=True,
        )


def test_doctor_requests_human_readable_health_output() -> None:
    """Doctor must delegate to Health using the text renderer."""

    result = run_doctor()

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Atlas Health Diagnostics" in result.stdout
    assert "Overall Status: HEALTHY" in result.stdout
    assert "CAPTURED_ARGUMENTS=--format text" in result.stdout


def test_doctor_propagates_health_engine_failure() -> None:
    """Doctor must preserve a failing Health exit status."""

    result = run_doctor(
        health_status=1,
    )

    assert result.returncode == 1
    assert "CAPTURED_ARGUMENTS=--format text" in result.stdout


def test_doctor_wrapper_contains_no_diagnostic_ownership() -> None:
    """The shell wrapper must remain a thin delegation boundary."""

    source = DOCTOR_SCRIPT.read_text(
        encoding="utf-8",
    )

    assert "atlas_health_python --format text" in source
    assert "docker " not in source
    assert "ATLAS_STORAGE_ROOT" not in source
    assert "atlas_section" not in source
    assert "Overall Status:" not in source
