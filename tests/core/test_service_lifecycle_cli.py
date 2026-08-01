from __future__ import annotations

import json
import subprocess
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

from atlas.service_lifecycle import ManagedService, ServiceLifecycleError
from atlas.service_lifecycle_cli import main

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ATLAS_CLI = PROJECT_ROOT / "scripts" / "atlas"


def sample_services() -> tuple[ManagedService, ...]:
    return (
        ManagedService(
            identifier="jellyfin",
            name="Jellyfin",
            provider="docker-compose",
            container_name="jellyfin",
        ),
        ManagedService(
            identifier="qbittorrent",
            name="Qbittorrent",
            provider="docker-compose",
            container_name="qbittorrent",
            dependencies=("gluetun",),
        ),
    )


def test_list_human_output() -> None:
    service = Mock()
    service.list_services.return_value = sample_services()
    output = StringIO()

    result = main(["list"], service=service, output=output)

    assert result == 0
    assert "Atlas Managed Services" in output.getvalue()
    assert "jellyfin" in output.getvalue()
    assert "Total: 2" in output.getvalue()


def test_list_json_output() -> None:
    service = Mock()
    service.list_services.return_value = sample_services()
    output = StringIO()

    result = main(["list", "--json"], service=service, output=output)
    payload = json.loads(output.getvalue())

    assert result == 0
    assert [item["identifier"] for item in payload] == [
        "jellyfin",
        "qbittorrent",
    ]


def test_list_error_output() -> None:
    service = Mock()
    service.list_services.side_effect = ServiceLifecycleError("failed")
    error = StringIO()

    result = main(["list"], service=service, error=error)

    assert result == 1
    assert "Service Lifecycle error: failed" in error.getvalue()


def test_service_help_dispatcher() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Project Atlas Service Lifecycle" in result.stdout


def test_unknown_service_command() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "unexpected"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Unknown service command: unexpected" in result.stderr


def test_global_help_registration() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "atlas service list [--json]" in result.stdout
