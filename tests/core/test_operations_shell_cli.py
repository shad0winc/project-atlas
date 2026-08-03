"""Shell integration tests for the Atlas Operations command."""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def prepare_cli(tmp_path: Path) -> tuple[Path, Path]:
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
        PROJECT_ROOT / "scripts" / "commands" / "operations.sh",
        commands / "operations.sh",
    )
    shutil.copy2(
        PROJECT_ROOT / "scripts" / "commands" / "help.sh",
        commands / "help.sh",
    )
    shutil.copy2(
        PROJECT_ROOT / "scripts" / "lib" / "common.sh",
        lib / "common.sh",
    )

    # The dispatcher sources every registered command module. Stub all
    # unrelated modules so this focused fixture tests Operations only.
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
        "backup",
        "test",
        "health",
        "scheduler",
        "user",
        "invite",
        "favorite",
        "retention",
        "cleanup",
        "discovery",
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

    (project / "config" / "modules" / "modules.conf").write_text(
        "\n",
        encoding="utf-8",
    )

    fake_python = bin_directory / "python3"
    fake_python.write_text(
        '''#!/usr/bin/env bash
printf '%s\\n' "$@" >"$ATLAS_TEST_CAPTURE"
exit "${ATLAS_TEST_PYTHON_STATUS:-0}"
''',
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


def test_operations_help_returns_zero(tmp_path: Path) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "help",
    )

    assert completed.returncode == 0
    assert "Atlas Operations" in completed.stdout
    assert "atlas operations report" in completed.stdout
    assert "atlas operations save" in completed.stdout
    assert "atlas operations latest" in completed.stdout
    assert "atlas operations history" in completed.stdout
    assert "atlas operations compare" in completed.stdout
    assert completed.stderr == ""
    assert not capture_path.exists()


def test_operations_defaults_to_help(tmp_path: Path) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
    )

    assert completed.returncode == 0
    assert "Atlas Operations" in completed.stdout
    assert not capture_path.exists()


def test_operations_report_forwards_to_python(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "report",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "report",
    ]


def test_operations_report_forwards_all_options(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "report",
        "--json",
        "--report-id",
        "daily-operations",
    )

    assert completed.returncode == 0

    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "report",
        "--json",
        "--report-id",
        "daily-operations",
    ]


def test_operations_preserves_python_exit_code(
    tmp_path: Path,
) -> None:
    completed, _ = run_atlas(
        tmp_path,
        "operations",
        "report",
        python_status=7,
    )

    assert completed.returncode == 7


def test_operations_rejects_unknown_subcommand(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "unknown",
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == (
        "Unknown operations command: unknown\n"
        "Run: atlas operations help\n"
    )
    assert not capture_path.exists()


def test_operations_help_rejects_extra_arguments(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "help",
        "extra",
    )

    assert completed.returncode == 2
    assert "does not accept additional arguments" in (
        completed.stderr
    )
    assert not capture_path.exists()


def test_central_help_lists_operations(
    tmp_path: Path,
) -> None:
    completed, _ = run_atlas(
        tmp_path,
        "help",
    )

    assert completed.returncode == 0
    assert (
        "atlas operations [help|report|save|latest|history|compare]"
        in completed.stdout
    )
    assert (
        "atlas operations report "
        "[--json] [--report-id REPORT_ID]"
        in completed.stdout
    )
    assert (
        "atlas operations save "
        "[--json] [--report-id REPORT_ID]"
        in completed.stdout
    )
    assert (
        "atlas operations latest [--json]"
        in completed.stdout
    )
    assert (
        "atlas operations history [--limit LIMIT] [--json]"
        in completed.stdout
    )
    assert (
        "atlas operations compare [--json] [--include-unchanged]"
        in completed.stdout
    )


def test_unknown_top_level_command_remains_unchanged(
    tmp_path: Path,
) -> None:
    completed, _ = run_atlas(
        tmp_path,
        "not-a-command",
    )

    assert completed.returncode == 1
    assert completed.stdout == (
        "Unknown command: not-a-command\n"
        "Run: atlas help\n"
    )


def test_operations_save_forwards_to_python(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "save",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "save",
    ]


def test_operations_save_forwards_all_options(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "save",
        "--json",
        "--report-id",
        "nightly-operations",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "save",
        "--json",
        "--report-id",
        "nightly-operations",
    ]


def test_operations_latest_forwards_to_python(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "latest",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "latest",
    ]


def test_operations_latest_forwards_json_option(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "latest",
        "--json",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "latest",
        "--json",
    ]


def test_operations_save_preserves_python_exit_code(
    tmp_path: Path,
) -> None:
    completed, _ = run_atlas(
        tmp_path,
        "operations",
        "save",
        python_status=6,
    )

    assert completed.returncode == 6


def test_operations_latest_preserves_python_exit_code(
    tmp_path: Path,
) -> None:
    completed, _ = run_atlas(
        tmp_path,
        "operations",
        "latest",
        python_status=5,
    )

    assert completed.returncode == 5


def test_operations_history_forwards_to_python(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "history",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "history",
    ]


def test_operations_history_forwards_options(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "history",
        "--limit",
        "10",
        "--json",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "history",
        "--limit",
        "10",
        "--json",
    ]


def test_operations_history_preserves_python_exit_code(
    tmp_path: Path,
) -> None:
    completed, _ = run_atlas(
        tmp_path,
        "operations",
        "history",
        python_status=7,
    )

    assert completed.returncode == 7


def test_operations_compare_forwards_to_python(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "compare",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "compare",
    ]


def test_operations_compare_forwards_options(
    tmp_path: Path,
) -> None:
    completed, capture_path = run_atlas(
        tmp_path,
        "operations",
        "compare",
        "--json",
        "--include-unchanged",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert capture_path.read_text(
        encoding="utf-8",
    ).splitlines() == [
        "-m",
        "atlas.operations_cli",
        "compare",
        "--json",
        "--include-unchanged",
    ]


def test_operations_compare_preserves_python_exit_code(
    tmp_path: Path,
) -> None:
    completed, _ = run_atlas(
        tmp_path,
        "operations",
        "compare",
        python_status=7,
    )

    assert completed.returncode == 7
