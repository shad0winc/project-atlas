"""Tests for the Atlas Operations comparison service."""

from __future__ import annotations

import pytest

from atlas.operations import (
    OperationFinding,
    OperationsChangeType,
    OperationsComparisonService,
    OperationsComparisonServiceError,
    OperationsReport,
    OperationsSection,
)


def finding(
    identifier: str,
    *,
    status: str = "healthy",
    severity: str = "info",
    message: str | None = None,
) -> OperationFinding:
    name = identifier.rsplit(".", 1)[-1].title()

    return OperationFinding(
        identifier=identifier,
        name=name,
        status=status,
        severity=severity,
        message=message or f"{name}: healthy",
    )


def report(
    report_id: str,
    generated_at: str,
    *,
    system: tuple[OperationFinding, ...] = (),
    containers: tuple[OperationFinding, ...] = (),
) -> OperationsReport:
    sections: list[OperationsSection] = []

    if system:
        sections.append(
            OperationsSection(
                identifier="system",
                name="System",
                findings=system,
            )
        )

    if containers:
        sections.append(
            OperationsSection(
                identifier="containers",
                name="Containers",
                findings=containers,
            )
        )

    return OperationsReport(
        report_id=report_id,
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="b16b5f66",
        generated_at=generated_at,
        sections=tuple(sections),
    )


def test_compare_identical_reports_has_no_differences() -> None:
    value = finding("system.hostname")

    previous = report(
        "previous",
        "2026-08-03T21:00:00Z",
        system=(value,),
    )
    current = report(
        "current",
        "2026-08-03T22:00:00Z",
        system=(value,),
    )

    comparison = OperationsComparisonService().compare(
        previous,
        current,
    )

    assert comparison.changes == ()
    assert comparison.difference_count == 0
    assert comparison.score_delta == 0


def test_compare_can_include_unchanged_findings() -> None:
    value = finding("system.hostname")

    comparison = OperationsComparisonService().compare(
        report(
            "previous",
            "2026-08-03T21:00:00Z",
            system=(value,),
        ),
        report(
            "current",
            "2026-08-03T22:00:00Z",
            system=(value,),
        ),
        include_unchanged=True,
    )

    assert len(comparison.changes) == 1
    assert comparison.unchanged_count == 1
    assert (
        comparison.changes[0].change_type
        is OperationsChangeType.UNCHANGED
    )


def test_compare_detects_changed_finding() -> None:
    before = finding("system.memory")
    after = finding(
        "system.memory",
        status="warning",
        severity="warning",
        message="Memory usage is elevated",
    )

    comparison = OperationsComparisonService().compare(
        report(
            "previous",
            "2026-08-03T21:00:00Z",
            system=(before,),
        ),
        report(
            "current",
            "2026-08-03T22:00:00Z",
            system=(after,),
        ),
    )

    assert comparison.changed_count == 1
    assert comparison.score_delta == -50
    assert comparison.attention_delta == 1
    assert comparison.changes[0].before == before
    assert comparison.changes[0].after == after


def test_compare_detects_added_and_removed_findings() -> None:
    removed = finding("system.kernel")
    added = finding("system.uptime")

    comparison = OperationsComparisonService().compare(
        report(
            "previous",
            "2026-08-03T21:00:00Z",
            system=(removed,),
        ),
        report(
            "current",
            "2026-08-03T22:00:00Z",
            system=(added,),
        ),
    )

    assert comparison.added_count == 1
    assert comparison.removed_count == 1
    assert comparison.difference_count == 2

    assert tuple(
        change.identifier
        for change in comparison.changes
    ) == (
        "system.kernel",
        "system.uptime",
    )


def test_compare_treats_section_move_as_remove_and_add() -> None:
    value = finding("shared.runtime")

    comparison = OperationsComparisonService().compare(
        report(
            "previous",
            "2026-08-03T21:00:00Z",
            system=(value,),
        ),
        report(
            "current",
            "2026-08-03T22:00:00Z",
            containers=(value,),
        ),
    )

    assert comparison.added_count == 1
    assert comparison.removed_count == 1

    assert tuple(
        (
            change.section.value,
            change.change_type.value,
        )
        for change in comparison.changes
    ) == (
        ("system", "removed"),
        ("containers", "added"),
    )


@pytest.mark.parametrize(
    ("field", "previous", "current", "message"),
    (
        (
            "previous",
            object(),
            report(
                "current",
                "2026-08-03T22:00:00Z",
            ),
            "previous must be an OperationsReport",
        ),
        (
            "current",
            report(
                "previous",
                "2026-08-03T21:00:00Z",
            ),
            object(),
            "current must be an OperationsReport",
        ),
    ),
)
def test_compare_validates_report_inputs(
    field: str,
    previous: object,
    current: object,
    message: str,
) -> None:
    del field

    with pytest.raises(
        OperationsComparisonServiceError,
        match=message,
    ):
        OperationsComparisonService().compare(
            previous,  # type: ignore[arg-type]
            current,  # type: ignore[arg-type]
        )


def test_compare_validates_include_unchanged() -> None:
    with pytest.raises(
        OperationsComparisonServiceError,
        match="include_unchanged must be boolean",
    ):
        OperationsComparisonService().compare(
            report(
                "previous",
                "2026-08-03T21:00:00Z",
            ),
            report(
                "current",
                "2026-08-03T22:00:00Z",
            ),
            include_unchanged=1,  # type: ignore[arg-type]
        )
