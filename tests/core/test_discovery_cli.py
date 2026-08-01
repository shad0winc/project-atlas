"""Contract tests for the Atlas Discovery CLI dispatcher."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ATLAS_CLI = PROJECT_ROOT / "scripts" / "atlas"


def run_atlas(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the Atlas CLI and capture its text output."""

    return subprocess.run(
        [
            str(ATLAS_CLI),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def repository_state() -> tuple[str, str]:
    """Return stable hashes of unstaged and staged repository changes."""

    worktree = subprocess.run(
        [
            "git",
            "diff",
            "--binary",
            "--no-ext-diff",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    ).stdout

    index = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--binary",
            "--no-ext-diff",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    ).stdout

    return (
        hashlib.sha256(worktree).hexdigest(),
        hashlib.sha256(index).hexdigest(),
    )


@pytest.mark.parametrize(
    "arguments",
    [
        (
            "discovery",
        ),
        (
            "discovery",
            "help",
        ),
        (
            "discovery",
            "-h",
        ),
        (
            "discovery",
            "--help",
        ),
    ],
)
def test_discovery_help_forms_succeed(
    arguments: tuple[str, ...],
) -> None:
    result = run_atlas(*arguments)

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Project Atlas Discovery" in result.stdout
    assert "atlas discovery indexers" in result.stdout
    assert "atlas discovery categories" in result.stdout
    assert "atlas discovery applications" in result.stdout
    assert "atlas discovery health" in result.stdout
    assert "atlas discovery report" in result.stdout


@pytest.mark.parametrize(
    "subcommand",
    [
        "indexers",
        "categories",
        "applications",
        "health",
        "report",
    ],
)
def test_registered_subcommands_are_explicitly_pending(
    subcommand: str,
) -> None:
    result = run_atlas(
        "discovery",
        subcommand,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert (
        "Discovery subcommand is not implemented yet: "
        f"{subcommand}"
    ) in result.stderr
    assert "Run: atlas discovery help" in result.stderr


def test_unknown_discovery_subcommand_returns_usage_error() -> None:
    result = run_atlas(
        "discovery",
        "unexpected",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert (
        "Unknown discovery command: unexpected"
        in result.stderr
    )
    assert "Run: atlas discovery help" in result.stderr


def test_global_help_registers_discovery_command() -> None:
    result = run_atlas("help")

    assert result.returncode == 0
    assert result.stderr == ""
    assert (
        "atlas discovery "
        "[help|indexers|categories|applications|health|report]"
        in result.stdout
    )


def test_discovery_dispatcher_does_not_modify_repository() -> None:
    before = repository_state()

    commands = [
        (
            "discovery",
        ),
        (
            "discovery",
            "help",
        ),
        (
            "discovery",
            "indexers",
        ),
        (
            "discovery",
            "unexpected",
        ),
    ]

    for arguments in commands:
        run_atlas(*arguments)

    after = repository_state()

    assert after == before
