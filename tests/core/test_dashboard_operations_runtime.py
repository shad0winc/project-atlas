from __future__ import annotations

import os
from pathlib import Path

import pytest

from atlas.dashboard_runtime import (
    DashboardRuntimeError,
    publish_operations_projection,
)
from atlas.operations import (
    OperationFinding,
    OperationsReport,
    OperationsSection,
)
from atlas.operations.repository import (
    FileOperationsRepository,
    OperationsReportNotFoundError,
)


def make_report(report_id: str, generated_at: str) -> OperationsReport:
    return OperationsReport(
        report_id=report_id,
        hostname="docker",
        atlas_version="1.0.0-rc.1",
        git_commit="d789b156",
        generated_at=generated_at,
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(
                    OperationFinding(
                        identifier=f"{report_id}.finding",
                        name="Finding",
                        status="healthy",
                        severity="info",
                        message="Healthy.",
                    ),
                ),
            ),
        ),
    )


def populate_source(root: Path, count: int) -> FileOperationsRepository:
    repository = FileOperationsRepository(root)
    for index in range(count):
        repository.save(
            make_report(
                f"report-{index}",
                f"2026-08-29T{index + 10:02d}:00:00Z",
            )
        )
    return repository


def test_projection_publishes_latest_and_two_history_reports(tmp_path: Path) -> None:
    source = populate_source(tmp_path / "source", 3)
    destination = tmp_path / "runtime" / "operations"
    current = publish_operations_projection(source.root, destination, history_limit=2)

    assert current.is_symlink()
    projected = FileOperationsRepository(current)
    assert projected.latest().report_id == "report-2"
    assert tuple(report.report_id for report in projected.history(limit=25)) == (
        "report-2",
        "report-1",
    )
    assert len(tuple(projected.history_directory.glob("*.json"))) == 2


def test_projection_refresh_selects_new_generation(tmp_path: Path) -> None:
    source = populate_source(tmp_path / "source", 3)
    destination = tmp_path / "runtime" / "operations"
    current = publish_operations_projection(source.root, destination)
    first_target = current.resolve()

    source.save(make_report("report-3", "2026-08-29T13:00:00Z"))
    current = publish_operations_projection(source.root, destination)
    second_target = current.resolve()

    assert second_target != first_target
    projected = FileOperationsRepository(current)
    assert projected.latest().report_id == "report-3"
    assert tuple(report.report_id for report in projected.history(limit=25)) == (
        "report-3",
        "report-2",
    )
    generations = tuple(
        item for item in (destination / "generations").iterdir() if item.is_dir()
    )
    assert len(generations) <= 2


def test_projection_preserves_runtime_permissions(tmp_path: Path) -> None:
    source = populate_source(tmp_path / "source", 2)
    destination = tmp_path / "runtime" / "operations"
    current = publish_operations_projection(source.root, destination)
    target = current.resolve()

    assert os.stat(destination).st_mode & 0o777 == 0o750
    assert os.stat(target).st_mode & 0o777 == 0o750
    assert os.stat(target / "history").st_mode & 0o777 == 0o750
    assert os.stat(target / "latest.json").st_mode & 0o777 == 0o640
    assert os.stat(destination).st_gid == 20000
    assert os.stat(target).st_gid == 20000
    assert os.stat(target / "latest.json").st_gid == 20000


def test_projection_rejects_missing_canonical_latest(tmp_path: Path) -> None:
    with pytest.raises(OperationsReportNotFoundError):
        publish_operations_projection(
            tmp_path / "missing-source",
            tmp_path / "runtime" / "operations",
        )


def test_projection_rejects_nonpositive_history_limit(tmp_path: Path) -> None:
    with pytest.raises(DashboardRuntimeError):
        publish_operations_projection(
            tmp_path / "source",
            tmp_path / "runtime",
            history_limit=0,
        )
