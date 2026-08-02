"""Contract tests for the Atlas Service Lifecycle CLI."""

from __future__ import annotations

import json
import subprocess
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from atlas.service_lifecycle import (
    DoctorCategory,
    DoctorFinding,
    DoctorReport,
    DoctorSeverity,
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRuntime,
    ImageReference,
    ServiceUpdate,
    UpdateReport,
    UpdateStatus,
    MaintenanceAction,
    MaintenanceRecord,
    MaintenanceReport,
    MaintenanceResult,
)
from atlas.service_lifecycle.service import (
    InfrastructureDependencyGraph,
    InfrastructureHealthReport,
    InfrastructureSummary,
    ServiceDependencyNode,
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


def sample_graph() -> InfrastructureDependencyGraph:
    jellyfin = ManagedService(
        identifier="jellyfin",
        name="Jellyfin",
        provider="docker-compose",
        compose_project="project-atlas",
    )
    jellyseerr = ManagedService(
        identifier="jellyseerr",
        name="Jellyseerr",
        provider="docker-compose",
        compose_project="project-atlas",
        dependencies=("jellyfin", "radarr"),
    )
    radarr = ManagedService(
        identifier="radarr",
        name="Radarr",
        provider="docker-compose",
        compose_project="project-atlas",
    )
    bazarr = ManagedService(
        identifier="bazarr",
        name="Bazarr",
        provider="docker-compose",
        compose_project="project-atlas",
    )

    return InfrastructureDependencyGraph(
        nodes=(
            ServiceDependencyNode(service=bazarr),
            ServiceDependencyNode(
                service=jellyfin,
                dependents=(jellyseerr,),
            ),
            ServiceDependencyNode(
                service=jellyseerr,
                dependencies=(jellyfin, radarr),
            ),
            ServiceDependencyNode(
                service=radarr,
                dependents=(jellyseerr,),
            ),
        ),
        evaluated_at="2026-08-01T23:15:00Z",
    )


def sample_doctor_report() -> DoctorReport:
    return DoctorReport(
        provider="docker-compose",
        findings=(
            DoctorFinding(
                identifier="jellyfin.runtime-stopped",
                severity=DoctorSeverity.ERROR,
                category=DoctorCategory.RUNTIME,
                code="runtime-stopped",
                message="Service Jellyfin is not running.",
                service_identifier="jellyfin",
                details={"state": "exited"},
                created_at="2026-08-02T01:00:00Z",
            ),
            DoctorFinding(
                identifier="qbittorrent.missing-health-check",
                severity=DoctorSeverity.WARNING,
                category=DoctorCategory.OBSERVABILITY,
                code="missing-health-check",
                message="Service qBittorrent has no configured health check.",
                service_identifier="qbittorrent",
                created_at="2026-08-02T01:00:00Z",
            ),
            DoctorFinding(
                identifier="homepage.mutable-image-tag",
                severity=DoctorSeverity.INFO,
                category=DoctorCategory.CONFIGURATION,
                code="mutable-image-tag",
                message="Service Homepage uses mutable image tag latest.",
                service_identifier="homepage",
                created_at="2026-08-02T01:00:00Z",
            ),
        ),
        evaluated_at="2026-08-02T01:00:00Z",
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
    assert "atlas service graph [--json]" in result.stdout


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


def test_service_help_registers_reporting_commands() -> None:
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

def test_graph_human_output() -> None:
    service = Mock()
    service.inspect_graph.return_value = sample_graph()
    output = StringIO()

    result = main(
        ["graph"],
        service=service,
        output=output,
    )

    rendered = output.getvalue()

    assert result == 0
    assert "Atlas Service Dependency Graph" in rendered
    assert "Provider:        docker-compose" in rendered
    assert "Relationships:   2" in rendered
    assert "jellyfin" in rendered
    assert "└── jellyseerr" in rendered
    assert "Standalone" in rendered
    assert "- bazarr" in rendered
    assert "Unresolved Dependencies" in rendered
    assert "None" in rendered
    service.inspect_graph.assert_called_once_with()


def test_graph_json_output() -> None:
    service = Mock()
    service.inspect_graph.return_value = sample_graph()
    output = StringIO()

    result = main(
        ["graph", "--json"],
        service=service,
        output=output,
    )

    payload = json.loads(output.getvalue())

    assert result == 0
    assert payload["provider"] == "docker-compose"
    assert payload["compose_project"] == "project-atlas"
    assert payload["total_services"] == 4
    assert payload["total_edges"] == 2
    assert [
        node["service"]["identifier"]
        for node in payload["roots"]
    ] == ["jellyfin", "radarr"]
    assert [
        service["identifier"]
        for service in payload["standalone"]
    ] == ["bazarr"]
    assert payload["unresolved"] == []
    service.inspect_graph.assert_called_once_with()


def test_graph_help_is_active() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "graph", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: atlas service graph" in result.stdout
    assert "--json" in result.stdout


def test_doctor_human_output() -> None:
    service = Mock()
    output = StringIO()

    with patch(
        "atlas.service_lifecycle_cli.ServiceDoctor"
    ) as doctor_class:
        doctor_class.return_value.diagnose.return_value = (
            sample_doctor_report()
        )
        result = main(
            ["doctor"],
            service=service,
            output=output,
        )

    rendered = output.getvalue()
    assert result == 0
    assert "Atlas Service Doctor" in rendered
    assert "Status: Unhealthy" in rendered
    assert "Errors:   1" in rendered
    assert "Warnings: 1" in rendered
    assert "INFO" in rendered
    assert "[jellyfin] Service Jellyfin is not running." in rendered
    doctor_class.assert_called_once_with(service)
    doctor_class.return_value.diagnose.assert_called_once_with()


def test_doctor_json_output() -> None:
    service = Mock()
    output = StringIO()

    with patch(
        "atlas.service_lifecycle_cli.ServiceDoctor"
    ) as doctor_class:
        doctor_class.return_value.diagnose.return_value = (
            sample_doctor_report()
        )
        result = main(
            ["doctor", "--json"],
            service=service,
            output=output,
        )

    payload = json.loads(output.getvalue())
    assert result == 0
    assert payload["status"] == "unhealthy"
    assert payload["provider"] == "docker-compose"
    assert payload["counts"] == {
        "critical": 0,
        "error": 1,
        "info": 1,
        "warning": 1,
    }
    assert payload["total_findings"] == 3
    assert payload["findings"][0]["service_identifier"] == "jellyfin"


def test_doctor_help_is_active() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "doctor", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "usage: atlas service doctor" in result.stdout
    assert "--json" in result.stdout



def sample_update_report() -> UpdateReport:
    mutable = ServiceUpdate(
        service_identifier="sonarr",
        service_name="Sonarr",
        current_image=ImageReference.parse(
            "lscr.io/linuxserver/sonarr:latest"
        ),
        status=UpdateStatus.MUTABLE_TAG,
        reason="The configured image uses the mutable latest tag.",
        evaluated_at="2026-08-02T02:10:00Z",
    )
    unknown = ServiceUpdate(
        service_identifier="jellyfin",
        service_name="Jellyfin",
        current_image=ImageReference.parse(
            "jellyfin/jellyfin:stable"
        ),
        status=UpdateStatus.UNKNOWN,
        reason="Registry comparison has not been performed.",
        evaluated_at="2026-08-02T02:10:00Z",
    )
    return UpdateReport(
        updates=(unknown, mutable),
        provider="docker-compose",
        evaluated_at="2026-08-02T02:10:00Z",
    )


def test_updates_human_output() -> None:
    service = Mock()
    output = StringIO()

    with patch(
        "atlas.service_lifecycle_cli.ServiceUpdateService",
    ) as update_service_class:
        update_service_class.return_value.inspect_updates.return_value = (
            sample_update_report()
        )
        result = main(["updates"], service=service, output=output)

    assert result == 0
    rendered = output.getvalue()
    assert "Atlas Service Updates" in rendered
    assert "Provider: docker-compose" in rendered
    assert "Mutable Tags:      1" in rendered
    assert "Unknown:           1" in rendered
    assert "[sonarr] Sonarr: mutable-tag" in rendered
    assert "[jellyfin] unknown" in rendered
    update_service_class.assert_called_once_with(service)
    update_service_class.return_value.inspect_updates.assert_called_once_with()


def test_updates_json_output() -> None:
    service = Mock()
    output = StringIO()
    report = sample_update_report()

    with patch(
        "atlas.service_lifecycle_cli.ServiceUpdateService",
    ) as update_service_class:
        update_service_class.return_value.inspect_updates.return_value = report
        result = main(
            ["updates", "--json"],
            service=service,
            output=output,
        )

    assert result == 0
    assert json.loads(output.getvalue()) == report.to_dict()


def test_updates_empty_inventory_output() -> None:
    service = Mock()
    output = StringIO()
    report = UpdateReport(
        updates=(),
        provider="unknown",
        evaluated_at="2026-08-02T02:10:00Z",
    )

    with patch(
        "atlas.service_lifecycle_cli.ServiceUpdateService",
    ) as update_service_class:
        update_service_class.return_value.inspect_updates.return_value = report
        result = main(["updates"], service=service, output=output)

    assert result == 0
    assert "Services Evaluated: 0" in output.getvalue()
    assert "No update items require attention." in output.getvalue()
    assert "All Services\n------------\nNone" in output.getvalue()


def test_updates_service_error_is_rendered() -> None:
    service = Mock()
    output = StringIO()
    error = StringIO()

    with patch(
        "atlas.service_lifecycle_cli.ServiceUpdateService",
    ) as update_service_class:
        update_service_class.return_value.inspect_updates.side_effect = (
            ServiceLifecycleError("update inspection failed")
        )
        result = main(
            ["updates"],
            service=service,
            output=output,
            error=error,
        )

    assert result == 1
    assert output.getvalue() == ""
    assert error.getvalue() == (
        "Service Lifecycle error: update inspection failed\n"
    )


def test_updates_help_is_active() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "updates", "--help"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: atlas service updates" in result.stdout
    assert "--json" in result.stdout


def sample_maintenance_report() -> MaintenanceReport:
    record = MaintenanceRecord(
        service_identifier="sonarr",
        service_name="Sonarr",
        action=MaintenanceAction.UPDATE_CHECK,
        result=MaintenanceResult.SUCCESS,
        started_at="2026-08-02T03:10:00Z",
        completed_at="2026-08-02T03:10:02Z",
        provider="docker-compose",
        summary="Update metadata inspected.",
    )
    return MaintenanceReport(
        records=(record,),
        provider="docker-compose",
        generated_at="2026-08-02T03:15:00Z",
    )


def test_history_human_output_all_services() -> None:
    service = Mock()
    output = StringIO()
    report = sample_maintenance_report()

    with patch(
        "atlas.service_lifecycle_cli."
        "ServiceMaintenanceHistoryService",
    ) as history_service_class:
        history_service_class.return_value.inspect_history.return_value = (
            report
        )

        result = main(
            ["history"],
            service=service,
            output=output,
        )

    assert result == 0
    rendered = output.getvalue()
    assert "Atlas Service Maintenance History" in rendered
    assert "Scope: All Managed Services" in rendered
    assert "Records: 1" in rendered
    assert "Success: 1" in rendered
    assert "[sonarr] update-check: success" in rendered
    history_service_class.assert_called_once_with(service)


def test_history_human_output_one_service() -> None:
    service = Mock()
    service.inspect_service.return_value = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )
    output = StringIO()
    report = sample_maintenance_report()

    with patch(
        "atlas.service_lifecycle_cli."
        "ServiceMaintenanceHistoryService",
    ) as history_service_class:
        (
            history_service_class
            .return_value
            .inspect_service_history
            .return_value
        ) = report

        result = main(
            ["history", " SONARR "],
            service=service,
            output=output,
        )

    assert result == 0
    assert "Scope: Service [sonarr]" in output.getvalue()
    service.inspect_service.assert_called_once_with(" SONARR ")
    (
        history_service_class
        .return_value
        .inspect_service_history
        .assert_called_once_with("sonarr")
    )


def test_history_json_output() -> None:
    service = Mock()
    output = StringIO()
    report = sample_maintenance_report()

    with patch(
        "atlas.service_lifecycle_cli."
        "ServiceMaintenanceHistoryService",
    ) as history_service_class:
        history_service_class.return_value.inspect_history.return_value = (
            report
        )

        result = main(
            ["history", "--json"],
            service=service,
            output=output,
        )

    assert result == 0
    assert json.loads(output.getvalue()) == report.to_dict()


def test_history_empty_output() -> None:
    service = Mock()
    output = StringIO()
    report = MaintenanceReport(
        records=(),
        provider="unknown",
        generated_at="2026-08-02T03:15:00Z",
    )

    with patch(
        "atlas.service_lifecycle_cli."
        "ServiceMaintenanceHistoryService",
    ) as history_service_class:
        history_service_class.return_value.inspect_history.return_value = (
            report
        )

        result = main(
            ["history"],
            service=service,
            output=output,
        )

    assert result == 0
    assert "Records: 0" in output.getvalue()
    assert "No maintenance history is available." in output.getvalue()


def test_history_service_error_is_rendered() -> None:
    service = Mock()
    output = StringIO()
    error = StringIO()

    with patch(
        "atlas.service_lifecycle_cli."
        "ServiceMaintenanceHistoryService",
    ) as history_service_class:
        history_service_class.return_value.inspect_history.side_effect = (
            ServiceLifecycleError("history inspection failed")
        )

        result = main(
            ["history"],
            service=service,
            output=output,
            error=error,
        )

    assert result == 1
    assert output.getvalue() == ""
    assert error.getvalue() == (
        "Service Lifecycle error: history inspection failed\n"
    )


def test_history_help_is_active() -> None:
    result = subprocess.run(
        [str(ATLAS_CLI), "service", "history", "--help"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage: atlas service history" in result.stdout
    assert "identifier" in result.stdout
    assert "--json" in result.stdout
