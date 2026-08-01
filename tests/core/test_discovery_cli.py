"""Contract tests for the Atlas Discovery CLI dispatcher."""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ATLAS_CLI = PROJECT_ROOT / "scripts" / "atlas"


def run_atlas(
    *arguments: str,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the Atlas CLI and capture its text output."""

    return subprocess.run(
        [
            str(ATLAS_CLI),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def discovery_test_environment() -> dict[str, str]:
    """Return non-secret configuration for parser-only CLI tests."""

    environment = os.environ.copy()
    environment["ATLAS_PROWLARR_URL"] = "http://127.0.0.1:1"
    environment["ATLAS_PROWLARR_API_KEY"] = "test-api-key"

    return environment


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


def test_health_subcommand_help_is_active() -> None:
    result = run_atlas(
        "discovery",
        "health",
        "--help",
        environment=discovery_test_environment(),
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "usage: atlas discovery health" in result.stdout
    assert "--json" in result.stdout


def test_applications_subcommand_help_is_active() -> None:
    result = run_atlas(
        "discovery",
        "applications",
        "--help",
        environment=discovery_test_environment(),
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "usage: atlas discovery applications" in result.stdout
    assert "--json" in result.stdout


def test_categories_subcommand_help_is_active() -> None:
    result = run_atlas(
        "discovery",
        "categories",
        "--help",
        environment=discovery_test_environment(),
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "usage: atlas discovery categories" in result.stdout
    assert "--json" in result.stdout


def test_indexers_subcommand_help_is_active() -> None:
    result = run_atlas(
        "discovery",
        "indexers",
        "--help",
        environment=discovery_test_environment(),
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "usage: atlas discovery indexers" in result.stdout
    assert "--json" in result.stdout


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
            "--help",
        ),
        (
            "discovery",
            "categories",
            "--help",
        ),
        (
            "discovery",
            "applications",
            "--help",
        ),
        (
            "discovery",
            "health",
            "--help",
        ),
        (
            "discovery",
            "unexpected",
        ),
    ]

    environment = discovery_test_environment()

    for arguments in commands:
        run_atlas(
            *arguments,
            environment=environment,
        )

    after = repository_state()

    assert after == before
