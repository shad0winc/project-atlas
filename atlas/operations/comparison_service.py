"""Comparison service for immutable Atlas Operations reports."""

from __future__ import annotations

from dataclasses import dataclass

from .comparison import (
    OperationsChangeType,
    OperationsComparison,
    OperationsFindingChange,
)
from .models import (
    OperationFinding,
    OperationsReport,
    OperationsSectionId,
)


class OperationsComparisonServiceError(ValueError):
    """Raised when Operations reports cannot be compared safely."""


@dataclass(frozen=True, slots=True)
class _IndexedFinding:
    """One finding paired with its owning section."""

    section: OperationsSectionId
    finding: OperationFinding


class OperationsComparisonService:
    """Compare two immutable Operations reports."""

    def compare(
        self,
        previous: OperationsReport,
        current: OperationsReport,
        *,
        include_unchanged: bool = False,
    ) -> OperationsComparison:
        """Return a deterministic comparison between two reports."""

        if not isinstance(previous, OperationsReport):
            raise OperationsComparisonServiceError(
                "previous must be an OperationsReport",
            )

        if not isinstance(current, OperationsReport):
            raise OperationsComparisonServiceError(
                "current must be an OperationsReport",
            )

        if not isinstance(include_unchanged, bool):
            raise OperationsComparisonServiceError(
                "include_unchanged must be boolean",
            )

        previous_findings = self._index_findings(previous)
        current_findings = self._index_findings(current)

        identifiers = sorted(
            set(previous_findings)
            | set(current_findings)
        )

        changes: list[OperationsFindingChange] = []

        for identifier in identifiers:
            before = previous_findings.get(identifier)
            after = current_findings.get(identifier)

            if before is None:
                if after is None:
                    raise OperationsComparisonServiceError(
                        "comparison index contains no finding",
                    )

                changes.append(
                    OperationsFindingChange(
                        section=after.section,
                        change_type=OperationsChangeType.ADDED,
                        after=after.finding,
                    )
                )
                continue

            if after is None:
                changes.append(
                    OperationsFindingChange(
                        section=before.section,
                        change_type=OperationsChangeType.REMOVED,
                        before=before.finding,
                    )
                )
                continue

            if before.section is not after.section:
                changes.extend(
                    (
                        OperationsFindingChange(
                            section=before.section,
                            change_type=OperationsChangeType.REMOVED,
                            before=before.finding,
                        ),
                        OperationsFindingChange(
                            section=after.section,
                            change_type=OperationsChangeType.ADDED,
                            after=after.finding,
                        ),
                    )
                )
                continue

            if before.finding != after.finding:
                changes.append(
                    OperationsFindingChange(
                        section=after.section,
                        change_type=OperationsChangeType.CHANGED,
                        before=before.finding,
                        after=after.finding,
                    )
                )
                continue

            if include_unchanged:
                changes.append(
                    OperationsFindingChange(
                        section=after.section,
                        change_type=OperationsChangeType.UNCHANGED,
                        before=before.finding,
                        after=after.finding,
                    )
                )

        return OperationsComparison(
            previous=previous,
            current=current,
            changes=tuple(changes),
        )

    @staticmethod
    def _index_findings(
        report: OperationsReport,
    ) -> dict[str, _IndexedFinding]:
        """Index globally unique report findings by identity."""

        return {
            finding.identifier: _IndexedFinding(
                section=section.identifier,
                finding=finding,
            )
            for section in report.sections
            for finding in section.findings
        }
