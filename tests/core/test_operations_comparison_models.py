"""Tests for Atlas Operations comparison contracts."""

from __future__ import annotations

import pytest

from atlas.operations.comparison import (
    OperationsChangeType,
    OperationsComparison,
    OperationsFindingChange,
)
from atlas.operations.models import (
    OperationFinding,
    OperationsModelError,
    OperationsSectionId,
    OperationsSeverity,
    OperationsStatus,
)


def finding(
    *,
    status: str = "healthy",
    severity: str = "info",
    message: str = "Hostname: docker",
) -> OperationFinding:
    return OperationFinding(
        identifier="system.hostname",
        name="Hostname",
        status=status,
        severity=severity,
        message=message,
        metadata={
            "hostname": "docker",
        },
    )


def test_change_type_values_are_stable() -> None:
    assert tuple(
        value.value
        for value in OperationsChangeType
    ) == (
        "added",
        "removed",
        "changed",
        "unchanged",
    )


def test_added_finding_change_normalizes_inputs() -> None:
    after = finding()

    change = OperationsFindingChange(
        section=" SYSTEM ",
        change_type=" ADDED ",
        after=after,
    )

    assert change.section is OperationsSectionId.SYSTEM
    assert change.change_type is OperationsChangeType.ADDED
    assert change.before is None
    assert change.after is after
    assert change.identifier == "system.hostname"
    assert change.name == "Hostname"


def test_removed_finding_change_is_valid() -> None:
    before = finding()

    change = OperationsFindingChange(
        section="system",
        change_type="removed",
        before=before,
    )

    assert change.change_type is OperationsChangeType.REMOVED
    assert change.before is before
    assert change.after is None


def test_changed_finding_change_is_valid() -> None:
    before = finding()
    after = finding(
        status="warning",
        severity="warning",
        message="Hostname lookup is degraded",
    )

    change = OperationsFindingChange(
        section="system",
        change_type="changed",
        before=before,
        after=after,
    )

    assert change.before is before
    assert change.after is after
    assert change.identifier == before.identifier


def test_unchanged_finding_change_is_valid() -> None:
    before = finding()
    after = finding()

    change = OperationsFindingChange(
        section="system",
        change_type="unchanged",
        before=before,
        after=after,
    )

    assert change.change_type is OperationsChangeType.UNCHANGED


def test_finding_change_round_trip() -> None:
    original = OperationsFindingChange(
        section="system",
        change_type="changed",
        before=finding(),
        after=finding(
            status="warning",
            severity="warning",
            message="Hostname lookup is degraded",
        ),
    )

    restored = OperationsFindingChange.from_dict(
        original.to_dict(),
    )

    assert restored == original
    assert restored.to_dict() == original.to_dict()


def test_finding_change_ignores_derived_fields() -> None:
    change = OperationsFindingChange.from_dict(
        {
            "identifier": "forged.identifier",
            "name": "Forged Name",
            "section": "system",
            "change_type": "added",
            "before": None,
            "after": finding().to_dict(),
        }
    )

    assert change.identifier == "system.hostname"
    assert change.name == "Hostname"


def test_finding_change_rejects_non_object_payload() -> None:
    with pytest.raises(
        OperationsModelError,
        match="finding change payload must be an object",
    ):
        OperationsFindingChange.from_dict(
            [],  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("change_type", "before", "after", "message"),
    (
        (
            "added",
            finding(),
            finding(),
            "added changes require only an after finding",
        ),
        (
            "removed",
            finding(),
            finding(),
            "removed changes require only a before finding",
        ),
        (
            "changed",
            None,
            finding(),
            "changed changes require before and after findings",
        ),
        (
            "unchanged",
            finding(),
            None,
            "unchanged changes require before and after findings",
        ),
    ),
)
def test_finding_change_validates_presence_contract(
    change_type: str,
    before: OperationFinding | None,
    after: OperationFinding | None,
    message: str,
) -> None:
    with pytest.raises(
        OperationsModelError,
        match=message,
    ):
        OperationsFindingChange(
            section="system",
            change_type=change_type,
            before=before,
            after=after,
        )


def test_changed_finding_rejects_equal_values() -> None:
    with pytest.raises(
        OperationsModelError,
        match="changed findings must not be equal",
    ):
        OperationsFindingChange(
            section="system",
            change_type="changed",
            before=finding(),
            after=finding(),
        )


def test_unchanged_finding_rejects_different_values() -> None:
    with pytest.raises(
        OperationsModelError,
        match="unchanged findings must be equal",
    ):
        OperationsFindingChange(
            section="system",
            change_type="unchanged",
            before=finding(),
            after=finding(
                status="warning",
                severity="warning",
                message="Hostname lookup is degraded",
            ),
        )


def test_finding_change_requires_matching_identifiers() -> None:
    other = OperationFinding(
        identifier="system.kernel",
        name="Kernel",
        status=OperationsStatus.WARNING,
        severity=OperationsSeverity.WARNING,
        message="Kernel changed",
    )

    with pytest.raises(
        OperationsModelError,
        match="must share an identifier",
    ):
        OperationsFindingChange(
            section="system",
            change_type="changed",
            before=finding(),
            after=other,
        )


def test_finding_change_validates_child_payload() -> None:
    with pytest.raises(
        OperationsModelError,
        match="after finding payload must be an object or null",
    ):
        OperationsFindingChange.from_dict(
            {
                "section": "system",
                "change_type": "added",
                "before": None,
                "after": [],
            }
        )


def report(
    *,
    report_id: str,
    generated_at: str,
    finding_value: OperationFinding,
) -> OperationsReport:
    from atlas.operations.models import (
        OperationsReport,
        OperationsSection,
    )

    return OperationsReport(
        report_id=report_id,
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="b16b5f66",
        generated_at=generated_at,
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(
                    finding_value,
                ),
            ),
        ),
    )


def test_operations_comparison_derives_summary() -> None:
    previous_finding = finding()
    current_finding = finding(
        status="warning",
        severity="warning",
        message="Hostname lookup is degraded",
    )

    comparison = OperationsComparison(
        previous=report(
            report_id="previous",
            generated_at="2026-08-03T21:00:00Z",
            finding_value=previous_finding,
        ),
        current=report(
            report_id="current",
            generated_at="2026-08-03T22:00:00Z",
            finding_value=current_finding,
        ),
        changes=(
            OperationsFindingChange(
                section="system",
                change_type="changed",
                before=previous_finding,
                after=current_finding,
            ),
        ),
    )

    assert comparison.status_changed is True
    assert comparison.score_delta == -50
    assert comparison.attention_delta == 1
    assert comparison.added_count == 0
    assert comparison.removed_count == 0
    assert comparison.changed_count == 1
    assert comparison.unchanged_count == 0
    assert comparison.difference_count == 1


def test_operations_comparison_orders_changes() -> None:
    hostname = finding()

    kernel = OperationFinding(
        identifier="system.kernel",
        name="Kernel",
        status="healthy",
        severity="info",
        message="Kernel: stable",
    )

    comparison = OperationsComparison(
        previous=report(
            report_id="previous",
            generated_at="2026-08-03T21:00:00Z",
            finding_value=hostname,
        ),
        current=report(
            report_id="current",
            generated_at="2026-08-03T22:00:00Z",
            finding_value=hostname,
        ),
        changes=(
            OperationsFindingChange(
                section="system",
                change_type="added",
                after=kernel,
            ),
            OperationsFindingChange(
                section="system",
                change_type="unchanged",
                before=hostname,
                after=hostname,
            ),
        ),
    )

    assert tuple(
        change.identifier
        for change in comparison.changes
    ) == (
        "system.hostname",
        "system.kernel",
    )


def test_operations_comparison_round_trip() -> None:
    previous_finding = finding()
    current_finding = finding(
        status="warning",
        severity="warning",
        message="Hostname lookup is degraded",
    )

    original = OperationsComparison(
        previous=report(
            report_id="previous",
            generated_at="2026-08-03T21:00:00Z",
            finding_value=previous_finding,
        ),
        current=report(
            report_id="current",
            generated_at="2026-08-03T22:00:00Z",
            finding_value=current_finding,
        ),
        changes=(
            OperationsFindingChange(
                section="system",
                change_type="changed",
                before=previous_finding,
                after=current_finding,
            ),
        ),
    )

    restored = OperationsComparison.from_dict(
        original.to_dict(),
    )

    assert restored == original
    assert restored.to_dict() == original.to_dict()


def test_operations_comparison_ignores_derived_summary() -> None:
    base = finding()

    comparison = OperationsComparison.from_dict(
        {
            "previous": report(
                report_id="previous",
                generated_at="2026-08-03T21:00:00Z",
                finding_value=base,
            ).to_dict(),
            "current": report(
                report_id="current",
                generated_at="2026-08-03T22:00:00Z",
                finding_value=base,
            ).to_dict(),
            "summary": {
                "status_changed": True,
                "score_delta": -100,
                "difference_count": 99,
            },
            "changes": [],
        }
    )

    assert comparison.status_changed is False
    assert comparison.score_delta == 0
    assert comparison.difference_count == 0


def test_operations_comparison_rejects_duplicate_changes() -> None:
    value = finding()

    duplicate = OperationsFindingChange(
        section="system",
        change_type="unchanged",
        before=value,
        after=value,
    )

    with pytest.raises(
        OperationsModelError,
        match="comparison changes must have unique identities",
    ):
        OperationsComparison(
            previous=report(
                report_id="previous",
                generated_at="2026-08-03T21:00:00Z",
                finding_value=value,
            ),
            current=report(
                report_id="current",
                generated_at="2026-08-03T22:00:00Z",
                finding_value=value,
            ),
            changes=(
                duplicate,
                duplicate,
            ),
        )


def test_operations_comparison_rejects_non_object() -> None:
    with pytest.raises(
        OperationsModelError,
        match="comparison payload must be an object",
    ):
        OperationsComparison.from_dict(
            [],  # type: ignore[arg-type]
        )


def test_operations_comparison_validates_change_collection() -> None:
    value = finding()

    with pytest.raises(
        OperationsModelError,
        match="comparison changes must be a list or tuple",
    ):
        OperationsComparison.from_dict(
            {
                "previous": report(
                    report_id="previous",
                    generated_at="2026-08-03T21:00:00Z",
                    finding_value=value,
                ).to_dict(),
                "current": report(
                    report_id="current",
                    generated_at="2026-08-03T22:00:00Z",
                    finding_value=value,
                ).to_dict(),
                "changes": {},
            }
        )
