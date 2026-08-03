"""Tests for immutable Atlas Operations report persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.atomic import write_json_atomic as atomic_write_json
from atlas.operations import (
    OperationFinding,
    OperationsReport,
    OperationsSection,
)
from atlas.operations.repository import (
    DEFAULT_OPERATIONS_DIRECTORY,
    FileOperationsRepository,
    OperationsReportNotFoundError,
    OperationsRepositoryError,
)


def make_report(
    *,
    report_id: str = "operations-report",
    generated_at: str = "2026-08-03T22:00:00Z",
    hostname: str = "docker",
) -> OperationsReport:
    return OperationsReport(
        report_id=report_id,
        hostname=hostname,
        atlas_version="0.9.0-rc.1",
        git_commit="491e0a77",
        generated_at=generated_at,
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
                        message=f"Hostname: {hostname}",
                    ),
                ),
            ),
        ),
    )


def test_default_operations_directory() -> None:
    assert DEFAULT_OPERATIONS_DIRECTORY == Path(
        "/mnt/storage/configs/atlas/operations",
    )


def test_repository_exposes_expected_paths(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    assert repository.root == tmp_path
    assert repository.history_directory == (
        tmp_path / "history"
    )
    assert repository.latest_path == (
        tmp_path / "latest.json"
    )


def test_repository_errors_are_runtime_errors() -> None:
    assert issubclass(
        OperationsRepositoryError,
        RuntimeError,
    )
    assert issubclass(
        OperationsReportNotFoundError,
        OperationsRepositoryError,
    )


def test_save_creates_snapshot_and_latest(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)
    report = make_report()

    snapshot = repository.save(report)

    assert snapshot == (
        tmp_path
        / "history"
        / "2026-08-03T22-00-00Z.json"
    )
    assert snapshot.is_file()
    assert repository.latest_path.is_file()

    assert json.loads(
        snapshot.read_text(encoding="utf-8")
    ) == report.to_dict()

    assert json.loads(
        repository.latest_path.read_text(
            encoding="utf-8",
        )
    ) == report.to_dict()


def test_save_returns_history_snapshot_path(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    result = repository.save(
        make_report(
            generated_at="2026-08-03T22:14:08Z",
        )
    )

    assert result.name == (
        "2026-08-03T22-14-08Z.json"
    )
    assert result.parent == repository.history_directory


def test_save_rejects_non_report(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    with pytest.raises(
        OperationsRepositoryError,
        match="report must be an OperationsReport",
    ):
        repository.save(
            object(),  # type: ignore[arg-type]
        )


def test_save_rejects_duplicate_snapshot(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)
    report = make_report()

    snapshot = repository.save(report)
    original = snapshot.read_text(encoding="utf-8")

    with pytest.raises(
        OperationsRepositoryError,
        match="snapshot already exists",
    ):
        repository.save(report)

    assert snapshot.read_text(
        encoding="utf-8",
    ) == original


def test_new_save_does_not_mutate_previous_snapshot(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    first = make_report(
        report_id="first-report",
        generated_at="2026-08-03T20:00:00Z",
    )
    second = make_report(
        report_id="second-report",
        generated_at="2026-08-03T21:00:00Z",
    )

    first_path = repository.save(first)
    first_payload = first_path.read_text(
        encoding="utf-8",
    )

    repository.save(second)

    assert first_path.read_text(
        encoding="utf-8",
    ) == first_payload
    assert repository.latest() == second


def test_latest_returns_persisted_report(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)
    report = make_report()

    repository.save(report)

    assert repository.latest() == report


def test_latest_rejects_missing_report(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    with pytest.raises(
        OperationsReportNotFoundError,
        match="latest Operations report was not found",
    ):
        repository.latest()


def test_history_is_empty_when_directory_is_missing(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    assert repository.history() == ()


def test_history_returns_newest_first(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    reports = (
        make_report(
            report_id="first",
            generated_at="2026-08-03T20:00:00Z",
        ),
        make_report(
            report_id="second",
            generated_at="2026-08-03T21:00:00Z",
        ),
        make_report(
            report_id="third",
            generated_at="2026-08-03T22:00:00Z",
        ),
    )

    for report in reports:
        repository.save(report)

    assert repository.history() == tuple(
        reversed(reports)
    )


def test_history_applies_limit(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    for hour in range(5):
        repository.save(
            make_report(
                report_id=f"report-{hour}",
                generated_at=(
                    f"2026-08-03T{hour + 10:02d}:00:00Z"
                ),
            )
        )

    result = repository.history(limit=2)

    assert tuple(
        report.report_id
        for report in result
    ) == (
        "report-4",
        "report-3",
    )


@pytest.mark.parametrize(
    "limit",
    (
        0,
        -1,
        True,
        1.5,
        "5",
        None,
    ),
)
def test_history_rejects_invalid_limit(
    tmp_path: Path,
    limit: object,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    with pytest.raises(
        OperationsRepositoryError,
        match="limit must be a positive integer",
    ):
        repository.history(
            limit=limit,  # type: ignore[arg-type]
        )


def test_latest_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    repository.latest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    repository.latest_path.write_text(
        "{invalid",
        encoding="utf-8",
    )

    with pytest.raises(
        OperationsRepositoryError,
        match="contains invalid JSON",
    ):
        repository.latest()


def test_latest_rejects_non_object_document(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    write_json_atomic = atomic_write_json
    write_json_atomic(
        repository.latest_path,
        [],
    )

    with pytest.raises(
        OperationsRepositoryError,
        match="must contain an object",
    ):
        repository.latest()


def test_latest_rejects_invalid_report_contract(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    write_json_atomic = atomic_write_json
    write_json_atomic(
        repository.latest_path,
        {
            "schema_version": 999,
        },
    )

    with pytest.raises(
        OperationsRepositoryError,
        match="Operations report is invalid",
    ):
        repository.latest()


def test_history_rejects_non_directory_path(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    repository.history_directory.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    repository.history_directory.write_text(
        "not a directory",
        encoding="utf-8",
    )

    with pytest.raises(
        OperationsRepositoryError,
        match="history path is not a directory",
    ):
        repository.history()


def test_history_rejects_corrupted_snapshot(
    tmp_path: Path,
) -> None:
    repository = FileOperationsRepository(tmp_path)

    repository.history_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    corrupted = (
        repository.history_directory
        / "2026-08-03T22-00-00Z.json"
    )
    corrupted.write_text(
        "{invalid",
        encoding="utf-8",
    )

    with pytest.raises(
        OperationsRepositoryError,
        match="contains invalid JSON",
    ):
        repository.history()


def test_save_uses_atomic_helper_for_snapshot_then_latest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FileOperationsRepository(tmp_path)
    report = make_report()
    calls: list[tuple[Path, object]] = []

    def fake_write(
        path: Path,
        value: object,
    ) -> None:
        calls.append((path, value))

    monkeypatch.setattr(
        "atlas.operations.repository.write_json_atomic",
        fake_write,
    )

    result = repository.save(report)

    assert result == repository.history_directory / (
        "2026-08-03T22-00-00Z.json"
    )
    assert calls == [
        (
            result,
            report.to_dict(),
        ),
        (
            repository.latest_path,
            report.to_dict(),
        ),
    ]


def test_snapshot_failure_prevents_latest_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FileOperationsRepository(tmp_path)
    calls: list[Path] = []

    def failing_write(
        path: Path,
        value: object,
    ) -> None:
        calls.append(path)
        raise OSError("disk unavailable")

    monkeypatch.setattr(
        "atlas.operations.repository.write_json_atomic",
        failing_write,
    )

    with pytest.raises(
        OperationsRepositoryError,
        match="unable to persist Operations report snapshot",
    ):
        repository.save(make_report())

    assert calls == [
        repository.history_directory
        / "2026-08-03T22-00-00Z.json"
    ]


def test_latest_failure_preserves_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FileOperationsRepository(tmp_path)
    original_write = atomic_write_json
    calls = 0

    def controlled_write(
        path: Path,
        value: object,
    ) -> None:
        nonlocal calls
        calls += 1

        if calls == 2:
            raise OSError("latest unavailable")

        original_write(path, value)

    monkeypatch.setattr(
        "atlas.operations.repository.write_json_atomic",
        controlled_write,
    )

    with pytest.raises(
        OperationsRepositoryError,
        match="snapshot persisted but latest report",
    ):
        repository.save(make_report())

    snapshot = (
        repository.history_directory
        / "2026-08-03T22-00-00Z.json"
    )

    assert snapshot.is_file()
    assert repository.latest_path.exists() is False


def test_public_operations_repository_exports() -> None:
    from atlas import operations

    assert (
        operations.DEFAULT_OPERATIONS_DIRECTORY
        is DEFAULT_OPERATIONS_DIRECTORY
    )
    assert (
        operations.FileOperationsRepository
        is FileOperationsRepository
    )
    assert (
        operations.OperationsReportNotFoundError
        is OperationsReportNotFoundError
    )
    assert (
        operations.OperationsRepositoryError
        is OperationsRepositoryError
    )
    assert operations.OperationsRepository.__name__ == (
        "OperationsRepository"
    )
