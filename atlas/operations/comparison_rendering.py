"""Renderers for Atlas Operations report comparisons."""

from __future__ import annotations

import json

from .comparison import (
    OperationsChangeType,
    OperationsComparison,
    OperationsFindingChange,
)
from .models import OperationsModelError


def render_comparison_human(
    comparison: OperationsComparison,
) -> str:
    """Render a concise human-readable Operations comparison."""

    if not isinstance(comparison, OperationsComparison):
        raise OperationsModelError(
            "comparison must be an OperationsComparison",
        )

    lines = [
        "Atlas Operations Comparison",
        "===========================",
        "",
        "Previous",
        "--------",
        f"Report:    {comparison.previous.report_id}",
        f"Generated: {comparison.previous.generated_at}",
        (
            "Status:    "
            f"{_status_label(comparison.previous.status.value)}"
        ),
        f"Score:     {comparison.previous.score}/100",
        "",
        "Current",
        "-------",
        f"Report:    {comparison.current.report_id}",
        f"Generated: {comparison.current.generated_at}",
        (
            "Status:    "
            f"{_status_label(comparison.current.status.value)}"
        ),
        f"Score:     {comparison.current.score}/100",
        "",
        "Summary",
        "-------",
        (
            "Status:    "
            f"{_status_label(comparison.previous.status.value)}"
            " -> "
            f"{_status_label(comparison.current.status.value)}"
        ),
        (
            "Score:     "
            f"{comparison.previous.score}/100"
            " -> "
            f"{comparison.current.score}/100"
            f" ({comparison.score_delta:+d})"
        ),
        (
            "Attention: "
            f"{len(comparison.previous.attention_findings)}"
            " -> "
            f"{len(comparison.current.attention_findings)}"
            f" ({comparison.attention_delta:+d})"
        ),
        f"Differences: {comparison.difference_count}",
        f"Added:       {comparison.added_count}",
        f"Removed:     {comparison.removed_count}",
        f"Changed:     {comparison.changed_count}",
    ]

    differences = tuple(
        change
        for change in comparison.changes
        if change.change_type
        is not OperationsChangeType.UNCHANGED
    )

    lines.extend(
        [
            "",
            "Changes",
            "-------",
        ]
    )

    if not differences:
        lines.append("None.")
        return "\n".join(lines)

    for change in differences:
        lines.extend(
            _render_change(change)
        )

    return "\n".join(lines)


def render_comparison_json(
    comparison: OperationsComparison,
) -> str:
    """Render deterministic comparison JSON."""

    if not isinstance(comparison, OperationsComparison):
        raise OperationsModelError(
            "comparison must be an OperationsComparison",
        )

    return json.dumps(
        comparison.to_dict(),
        indent=2,
        sort_keys=True,
    )


def _render_change(
    change: OperationsFindingChange,
) -> list[str]:
    marker = {
        OperationsChangeType.ADDED: "+",
        OperationsChangeType.REMOVED: "-",
        OperationsChangeType.CHANGED: "~",
        OperationsChangeType.UNCHANGED: "=",
    }[change.change_type]

    lines = [
        "",
        (
            f"{marker} [{change.section.value}] "
            f"{change.name} ({change.identifier})"
        ),
        f"  Type: {change.change_type.value.title()}",
    ]

    if change.before is not None:
        lines.extend(
            [
                (
                    "  Before: "
                    f"{_status_label(change.before.status.value)}"
                    f" — {change.before.message}"
                ),
            ]
        )

    if change.after is not None:
        lines.extend(
            [
                (
                    "  After:  "
                    f"{_status_label(change.after.status.value)}"
                    f" — {change.after.message}"
                ),
            ]
        )

    return lines


def _status_label(value: str) -> str:
    return value.replace("_", " ").title()
