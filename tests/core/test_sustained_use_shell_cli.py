"""Shell integration tests for the Atlas Sustained Use command."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def prepare_cli(tmp_path: Path) -> tuple[Path, Path]:
    """Create a focused Atlas shell dispatcher fixture."""
    project = tmp_path / "project-atlas"
    scripts = project / "scripts"
    commands = scripts / "commands"
    lib = scripts / "lib"
    bin_directory = tmp_path / "bin"
    capture_path = tmp_path / "python-arguments.txt"

    commands.mkdir(parents=True)
    lib.mkdir(parents=True)
    bin_directory.mkdir()

    shutil.copy2(
        PROJECT_ROOT / "scripts" / "atlas",
        scripts / "atlas",
    )
    shutil.copy2(
        PROJECT_ROOT
        / "scripts"
        / "commands"
        / "sustained-use.sh",
        commands / "sustained-use.sh",
    )
    shutil.copy2(
        PROJECT_ROOT / "scripts" / "commands" / "help.sh",
        commands / "help.sh",
    )
    shutil.copy2(
        PROJECT_ROOT / "scripts" / "lib" / "common.sh",
        lib / "common.sh",
    )

    # The root dispatcher sources every registered command module.
    # Stub unrelated modules so this fixture owns only Sustained Use.
    command_names = (
        "version",
        "status",
        "services",
        "service",
        "urls",
        "git",
        "restart",
        "logs",
        "ari",
        "module",
        "event",
        "verify",
        "doctor",
        "update",
        "maintenance",
        "deployment",
        "backup",
        "restore",
        "test",
        "health",
        "scheduler",
        "user",
        "invite",
        "favorite",
        "retention",
        "cleanup",
        "discovery",
        "operations",
    )

    for command_name in command_names:
        (commands / f"{command_name}.sh").write_text(
            "\n",
            encoding="utf-8",
        )

    (project / "config").mkdir()
    (project / "config" / "modules").mkdir()

    (project / "config" / "atlas.conf").write_text(
        (
            f'ATLAS_PROJECT_DIR="{project}"\n'
            'ATLAS_CONFIG_DIR="/tmp"\n'
            'ATLAS_BACKUP_DIR="/tmp"\n'
        ),
        encoding="utf-8",
    )

    (
        project
        / "config"
        / "modules"
        / "modules.conf"
    ).write_text(
        "\n",
        encoding="utf-8",
    )

    fake_python = bin_directory / "python3"
    fake_python.write_text(
        """#!/usr/bin/env bash
printf '%s\\n' "$@" >"$ATLAS_TEST_CAPTURE"
exit "${ATLAS_TEST_PYTHON_STATUS:-0}"
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    atlas_script = scripts / "atlas"
    atlas_script.chmod(0o755)

    return atlas_script, capture_path


def run_atlas(
    tmp_path: Path,
    *arguments: str,
    python_status: int = 0,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the focused Atlas shell dispatcher."""
    atlas_script, capture_path = prepare_cli(tmp_path)

    environment = os.environ.copy()
    environment["PATH"] = (
        str(tmp_path / "bin")
        + os.pathsep
        + environment["PATH"]
    )
    environment["ATLAS_TEST_CAPTURE"] = str(capture_path)
    environment["ATLAS_TEST_PYTHON_STATUS"] = str(
        python_status
    )

    completed = subprocess.run(
        [
            str(atlas_script),
            *arguments,
        ],
        cwd=atlas_script.parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    return completed, capture_path


def test_sustained_use_forwards_to_python(
    tmp_path: Path,
) -> None:
    """The shell command must delegate to the Python CLI."""
    completed, capture_path = run_atlas(
        tmp_path,
        "sustained-use",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.sustained_use.cli",
    ]


def test_sustained_use_forwards_all_arguments(
    tmp_path: Path,
) -> None:
    """Arguments must cross the shell boundary unchanged."""
    completed, capture_path = run_atlas(
        tmp_path,
        "sustained-use",
        "status",
        "--json",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.sustained_use.cli",
        "status",
        "--json",
    ]


def test_sustained_use_preserves_python_exit_code(
    tmp_path: Path,
) -> None:
    """Python failures must propagate through the root CLI."""
    completed, capture_path = run_atlas(
        tmp_path,
        "sustained-use",
        "status",
        python_status=7,
    )

    assert completed.returncode == 7
    assert capture_path.exists()


def test_root_help_registers_sustained_use(
    tmp_path: Path,
) -> None:
    """Root help must advertise the Sustained Use family."""
    completed, capture_path = run_atlas(
        tmp_path,
        "help",
    )

    assert completed.returncode == 0
    assert "atlas sustained-use [--help]" in completed.stdout
    assert completed.stderr == ""
    assert not capture_path.exists()
