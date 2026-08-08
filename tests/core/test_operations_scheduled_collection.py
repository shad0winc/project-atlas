"""Tests for the Atlas Operations scheduled collection callback."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

from atlas.operations import (
    OperationFinding,
    OperationsReport,
    OperationsSection,
)
from atlas.operations_scheduled_collection import (
    collect_and_persist,
    main,
    render_result,
)


def operations_report() -> OperationsReport:
    return OperationsReport(
        report_id="scheduled-operations",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="3c991eb1",
        generated_at="2026-08-04T00:30:00Z",
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(
                    OperationFinding(
                        identifier="system.hostname",
                        name="Hostname",
                        status="healthy",
                        severity="info",
                        message="Hostname: docker",
                    ),
                ),
            ),
        ),
    )


class FakeService:
    def __init__(
        self,
        report: OperationsReport,
    ) -> None:
        self.report = report
        self.collect_count = 0

    def collect(self) -> OperationsReport:
        self.collect_count += 1
        return self.report


class FakeRepository:
    def __init__(
        self,
        snapshot_path: Path,
    ) -> None:
        self.snapshot_path = snapshot_path
        self.saved: list[OperationsReport] = []

    def save(
        self,
        report: OperationsReport,
    ) -> Path:
        self.saved.append(report)
        return self.snapshot_path


def test_collect_and_persist_uses_service_and_repository(
    tmp_path: Path,
) -> None:
    report = operations_report()
    snapshot_path = (
        tmp_path
        / "history"
        / "2026-08-04T00-30-00Z.json"
    )
    service = FakeService(report)
    repository = FakeRepository(snapshot_path)

    restored_report, restored_path = collect_and_persist(
        service_factory=lambda: service,  # type: ignore[arg-type]
        repository_factory=lambda: repository,
    )

    assert restored_report is report
    assert restored_path == snapshot_path
    assert service.collect_count == 1
    assert repository.saved == [report]


def test_render_result_is_deterministic(
    tmp_path: Path,
) -> None:
    report = operations_report()
    snapshot_path = tmp_path / "snapshot.json"

    payload = json.loads(
        render_result(
            report,
            snapshot_path,
        )
    )

    assert payload == {
        "generated_at": "2026-08-04T00:30:00Z",
        "report_id": "scheduled-operations",
        "score": 100,
        "snapshot_path": str(snapshot_path),
        "status": "healthy",
    }


def test_main_executes_scheduled_collection(
    tmp_path: Path,
) -> None:
    report = operations_report()
    snapshot_path = tmp_path / "snapshot.json"
    service = FakeService(report)
    repository = FakeRepository(snapshot_path)
    stdout = StringIO()
    stderr = StringIO()

    result = main(
        [],
        service_factory=lambda: service,  # type: ignore[arg-type]
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert stderr.getvalue() == ""
    assert repository.saved == [report]

    payload = json.loads(
        stdout.getvalue()
    )

    assert payload["report_id"] == "scheduled-operations"
    assert payload["snapshot_path"] == str(snapshot_path)


def test_main_rejects_arguments() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["unexpected"],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 2
    assert stdout.getvalue() == ""
    assert "arguments are not supported" in stderr.getvalue()


def test_main_normalizes_collection_failure() -> None:
    class BrokenService:
        def collect(self) -> OperationsReport:
            raise RuntimeError("collection unavailable")

    stdout = StringIO()
    stderr = StringIO()

    result = main(
        [],
        service_factory=lambda: BrokenService(),  # type: ignore[arg-type]
        repository_factory=lambda: FakeRepository(
            Path("/tmp/unused.json"),
        ),
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 1
    assert stdout.getvalue() == ""
    assert (
        "Operations scheduled collection failed: "
        "collection unavailable"
        in stderr.getvalue()
    )


def test_collect_and_persist_validates_service_factory() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "service_factory must return an "
            "Operations collection service"
        ),
    ):
        collect_and_persist(
            service_factory=lambda: object(),  # type: ignore[arg-type]
            repository_factory=lambda: FakeRepository(
                Path("/tmp/unused.json"),
            ),
        )


def test_collect_and_persist_validates_repository_result() -> None:
    class InvalidRepository:
        def save(
            self,
            report: OperationsReport,
        ) -> str:
            del report
            return "/tmp/not-a-path.json"

    with pytest.raises(
        TypeError,
        match="Operations repository save must return a Path",
    ):
        collect_and_persist(
            service_factory=lambda: FakeService(  # type: ignore[arg-type]
                operations_report(),
            ),
            repository_factory=lambda: InvalidRepository(),
        )


def test_default_repository_factory_uses_runtime_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from atlas.operations import FileOperationsRepository
    from atlas.operations_scheduled_collection import (
        default_repository_factory,
    )

    monkeypatch.setenv(
        "ATLAS_OPERATIONS_DIRECTORY",
        str(tmp_path),
    )

    repository = default_repository_factory()

    assert isinstance(
        repository,
        FileOperationsRepository,
    )
    assert repository.root == tmp_path


def test_default_repository_factory_rejects_empty_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from atlas.operations_scheduled_collection import (
        default_repository_factory,
    )

    monkeypatch.setenv(
        "ATLAS_OPERATIONS_DIRECTORY",
        "   ",
    )

    with pytest.raises(
        ValueError,
        match="ATLAS_OPERATIONS_DIRECTORY cannot be empty",
    ):
        default_repository_factory()
