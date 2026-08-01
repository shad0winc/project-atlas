"""Contract tests for the Atlas Service Lifecycle CLI."""

from __future__ import annotations

import json
import subprocess
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

from atlas.service_lifecycle import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRuntime,
)
from atlas.service_lifecycle.service import (
    InfrastructureHealthReport,
    InfrastructureSummary,
    ServiceHealthEntry,
    ServiceRuntimeEntry,
)
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
            dependencies=(
                "gluetun",
            ),
        ),
    )


def sample_runtime() -> ServiceRuntime:
    return ServiceRuntime(
        state="running",
        health="healthy",
        image=ServiceImage(
            reference="jellyfin/jellyfin:latest",
            repository="jellyfin/jellyfin",
            tag="latest",
            image_id="sha256:" + ("a" * 64),
        ),
        restart_count=0,
        started_at="2026-08-01T12:00:00Z",
        exit_code=0,
        status_message="running",
    )


def sample_health() -> ServiceHealth:
    return ServiceHealth(
        status=ServiceHealthStatus.HEALTHY,
        score=100,
        evaluated_at="2026-08-01T12:05:00Z",
    )


def sample_health_report() -> InfrastructureHealthReport:
    services = sample_services()
    return InfrastructureHealthReport(
        entries=(
            ServiceHealthEntry(
                service=services[0],
                health=sample_health(),
            ),
            ServiceHealthEntry(
                service=services[1],
                health=ServiceHealth(
                    status=ServiceHealthStatus.DEGRADED,
                    score=80,
                    warnings=(
                        "No Docker health check configured",
                    ),
                    evaluated_at="2026-08-01T12:05:00Z",
                ),
            ),
        ),
        score=90,
        status="healthy",
        evaluated_at="2026-08-01T12:05:00Z",
    )


def sample_summary() -> InfrastructureSummary:
    services = sample_services()
    return InfrastructureSummary(
        runtime_entries=(
            ServiceRuntimeEntry(
                service=services[0],
                runtime=sample_runtime(),
            ),
            ServiceRuntimeEntry(
                service=services[1],
                runtime=ServiceRuntime(
                    state="exited",
                    health="unknown",
                    image=ServiceImage(
                        reference="qbittorrent:latest",
                    ),
                    exit_code=0,
                ),
            ),
        ),
        health=sample_health_report(),
        evaluated_at="2026-08-01T12:05:00Z",
    )


def test_list_human_output() -> None:
    service = Mock()
    service.list_services.return_value = sample_services()
    output = StringIO()

    result = main(
        [
            "list",
        ],
        service=service,
        output=output,
    )

    assert result == 0
    assert "Atlas Managed Services" in output.getvalue()
    assert "jellyfin" in output.getvalue()
    assert "Total: 2" in output.getvalue()


def test_list_json_output() -> None:
    service = Mock()
    service.list_services.return_value = sample_services()
    output = StringIO()

    result = main(
        [
            "list",
            "--json",
        ],
        service=service,
        output=output,
    )
    payload = json.loads(output.getvalue())

    assert result == 0
    assert [
        item["identifier"]
        for item in payload
    ] == [
        "jellyfin",
        "qbittorrent",
    ]


def test_list_error_output() -> None:
    service = Mock()
    service.list_services.side_effect = ServiceLifecycleError(
        "failed",
    )
    error = StringIO()

    result = main(
        [
            "list",
        ],
        service=service,
        error=error,
    )

    assert result == 1
    assert "Service Lifecycle error: failed" in error.getvalue()


def test_show_human_output() -> None:
    service = Mock()
    service.inspect_service.return_value = sample_services()[0]
    service.inspect_runtime.return_value = sample_runtime()
    service.inspect_health.return_value = sample_health()
    output = StringIO()

    result = main(
        [
            "show",
            "jellyfin",
        ],
        service=service,
        output=output,
    )

    rendered = output.getvalue()

    assert result == 0
    assert "Identifier: jellyfin" in rendered
    assert "State: running" in rendered
    assert "Reference: jellyfin/jellyfin:latest" in rendered
    assert "Status: healthy" in rendered
    assert "Score: 100/100" in rendered

    service.inspect_service.assert_called_once_with("jellyfin")
    service.inspect_runtime.assert_called_once_with("jellyfin")
    service.inspect_health.assert_called_once_with("jellyfin")


def test_show_json_output() -> None:
    service = Mock()
    service.inspect_service.return_value = sample_services()[0]
    service.inspect_runtime.return_value = sample_runtime()
    service.inspect_health.return_value = sample_health()
    output = StringIO()

    result = main(
        [
            "show",
            "jellyfin",
            "--json",
        ],
        service=service,
        output=output,
    )

    payload = json.loads(output.getvalue())

    assert result == 0
    assert payload["service"]["identifier"] == "jellyfin"
    assert payload["runtime"]["state"] == "running"
    assert payload["runtime"]["image"]["tag"] == "latest"
    assert payload["health"]["status"] == "healthy"
    assert payload["health"]["score"] == 100


def test_show_error_output() -> None:
    service = Mock()
    service.inspect_service.side_effect = ServiceLifecycleError(
        "service not found",
    )
    error = StringIO()

    result = main(
        [
            "show",
            "missing",
        ],
        service=service,
        error=error,
    )

    assert result == 1
    assert (
        "Service Lifecycle error: service not found"
        in error.getvalue()
    )


def test_service_help_dispatcher() -> None:
    result = subprocess.run(
        [
            str(ATLAS_CLI),
            "service",
            "help",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Project Atlas Service Lifecycle" in result.stdout
    assert (
        "atlas service show <identifier> [--json]"
        in result.stdout
    )
    assert "atlas service summary [--json]" in result.stdout


def test_show_help_is_active() -> None:
    result = subprocess.run(
        [
            str(ATLAS_CLI),
            "service",
            "show",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "usage: atlas service show" in result.stdout
    assert "--json" in result.stdout


def test_unknown_service_command() -> None:
    result = subprocess.run(
        [
            str(ATLAS_CLI),
            "service",
            "unexpected",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert (
        "Unknown service command: unexpected"
        in result.stderr
    )


def test_global_help_registration() -> None:
    result = subprocess.run(
        [
            str(ATLAS_CLI),
            "help",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "atlas service list [--json]" in result.stdout
    assert (
        "atlas service show <identifier> [--json]"
        in result.stdout
    )

def test_runtime_human_output() -> None:
    service = Mock()
    service.inspect_runtime.return_value = sample_runtime()
    output = StringIO()

    result = main(
        ["runtime", "jellyfin"],
        service=service,
        output=output,
    )

    rendered = output.getvalue()

    assert result == 0
    assert "Atlas Service Runtime" in rendered
    assert "State: running" in rendered
    assert "Docker Health: healthy" in rendered
    assert "Image: jellyfin/jellyfin:latest" in rendered
    service.inspect_runtime.assert_called_once_with("jellyfin")


def test_runtime_json_output() -> None:
    service = Mock()
    service.inspect_runtime.return_value = sample_runtime()
    output = StringIO()

    result = main(
        ["runtime", "jellyfin", "--json"],
        service=service,
        output=output,
    )

    payload = json.loads(output.getvalue())

    assert result == 0
    assert payload["state"] == "running"
    assert payload["health"] == "healthy"
    assert payload["image"]["reference"] == (
        "jellyfin/jellyfin:latest"
    )


def test_health_human_output() -> None:
    service = Mock()
    service.inspect_health.return_value = sample_health()
    output = StringIO()

    result = main(
        ["health", "jellyfin"],
        service=service,
        output=output,
    )

    rendered = output.getvalue()

    assert result == 0
    assert "Atlas Service Health" in rendered
    assert "Status: healthy" in rendered
    assert "Score: 100/100" in rendered
    assert "Warnings: None" in rendered
    service.inspect_health.assert_called_once_with("jellyfin")


def test_health_json_output() -> None:
    service = Mock()
    service.inspect_health.return_value = sample_health()
    output = StringIO()

    result = main(
        ["health", "jellyfin", "--json"],
        service=service,
        output=output,
    )

    payload = json.loads(output.getvalue())

    assert result == 0
    assert payload["status"] == "healthy"
    assert payload["score"] == 100
    assert payload["warnings"] == []
    assert payload["errors"] == []


def test_aggregate_health_human_output() -> None:
    service = Mock()
    service.inspect_health_report.return_value = sample_health_report()
    output = StringIO()

    result = main(
        ["health"],
        service=service,
        output=output,
    )

    rendered = output.getvalue()

    assert result == 0
    assert "Atlas Infrastructure Health" in rendered
    assert "Overall Score: 90/100" in rendered
    assert "Status: Healthy" in rendered
    assert "Healthy:     1" in rendered
    assert "Degraded:    1" in rendered
    assert "- qbittorrent" in rendered
    assert "No Docker health check configured" in rendered
    assert "Evaluated: 2026-08-01T12:05:00Z" in rendered
    service.inspect_health_report.assert_called_once_with()
    service.inspect_health.assert_not_called()


def test_aggregate_health_json_output() -> None:
    service = Mock()
    service.inspect_health_report.return_value = sample_health_report()
    output = StringIO()

    result = main(
        ["health", "--json"],
        service=service,
        output=output,
    )

    payload = json.loads(output.getvalue())

    assert result == 0
    assert payload["status"] == "healthy"
    assert payload["score"] == 90
    assert payload["total_services"] == 2
    assert payload["counts"] == {
        "healthy": 1,
        "degraded": 1,
        "unhealthy": 0,
        "unknown": 0,
    }
    assert [
        entry["service"]["identifier"]
        for entry in payload["attention_required"]
    ] == ["qbittorrent"]
    assert payload["warnings"] == [
        "qbittorrent: No Docker health check configured",
    ]
    assert len(payload["services"]) == 2
    service.inspect_health_report.assert_called_once_with()
    service.inspect_health.assert_not_called()



def test_summary_human_output() -> None:
    service = Mock()
    service.inspect_summary.return_value = sample_summary()
    output = StringIO()

    result = main(
        ["summary"],
        service=service,
        output=output,
    )

    rendered = output.getvalue()

    assert result == 0
    assert "Atlas Infrastructure Summary" in rendered
    assert "Provider:        docker-compose" in rendered
    assert "Total:       2" in rendered
    assert "Running:     1" in rendered
    assert "Stopped:     1" in rendered
    assert "Healthy:     1" in rendered
    assert "Degraded:    1" in rendered
    assert "Overall Score: 90/100" in rendered
    assert "Attention Required: 1" in rendered
    service.inspect_summary.assert_called_once_with()


def test_summary_json_output() -> None:
    service = Mock()
    service.inspect_summary.return_value = sample_summary()
    output = StringIO()

    result = main(
        ["summary", "--json"],
        service=service,
        output=output,
    )

    payload = json.loads(output.getvalue())

    assert result == 0
    assert payload["provider"] == "docker-compose"
    assert payload["total_services"] == 2
    assert payload["service_counts"] == {
        "enabled": 2,
        "disabled": 0,
    }
    assert payload["runtime_counts"] == {
        "running": 1,
        "stopped": 1,
        "restarting": 0,
        "failed": 0,
        "unknown": 0,
    }
    assert payload["health_counts"]["degraded"] == 1
    assert payload["score"] == 90
    assert payload["status"] == "healthy"
    service.inspect_summary.assert_called_once_with()


def test_summary_help_is_active() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "summary", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: atlas service summary" in result.stdout
    assert "--json" in result.stdout

def test_runtime_help_is_active() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "runtime", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: atlas service runtime" in result.stdout
    assert "--json" in result.stdout


def test_health_help_is_active() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "health", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: atlas service health" in result.stdout
    assert "--json" in result.stdout


def test_service_help_registers_runtime_health_and_summary() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert (
        "atlas service runtime <identifier> [--json]"
        in result.stdout
    )
    assert "atlas service health [--json]" in result.stdout
    assert (
        "atlas service health <identifier> [--json]"
        in result.stdout
    )
    assert "atlas service summary [--json]" in result.stdout
