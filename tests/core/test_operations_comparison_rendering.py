"""Tests for Atlas Operations comparison renderers."""

from __future__ import annotations

import json

import pytest

from atlas.operations import (
    OperationFinding,
    OperationsComparison,
    OperationsFindingChange,
    OperationsModelError,
    OperationsReport,
    OperationsSection,
)
from atlas.operations.comparison_rendering import (
    render_comparison_human,
    render_comparison_json,
)


def report(
    report_id: str,
    generated_at: str,
    finding: OperationFinding,
) -> OperationsReport:
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
                findings=(finding,),
            ),
        ),
    )


def healthy_finding() -> OperationFinding:
    return OperationFinding(
        identifier="system.memory",
        name="Memory",
        status="healthy",
        severity="info",
        message="Memory usage is healthy",
    )


def warning_finding() -> OperationFinding:
    return OperationFinding(
        identifier="system.memory",
        name="Memory",
        status="warning",
        severity="warning",
        message="Memory usage is elevated",
    )


def changed_comparison() -> OperationsComparison:
    before = healthy_finding()
    after = warning_finding()

    return OperationsComparison(
        previous=report(
            "previous-report",
            "2026-08-03T21:00:00Z",
            before,
        ),
        current=report(
            "current-report",
            "2026-08-03T22:00:00Z",
            after,
        ),
        changes=(
            OperationsFindingChange(
                section="system",
                change_type="changed",
                before=before,
                after=after,
            ),
        ),
    )


def test_human_renderer_renders_report_context() -> None:
    rendered = render_comparison_human(
        changed_comparison(),
    )

    assert rendered.startswith(
        "Atlas Operations Comparison\n"
        "===========================\n"
    )
    assert "Report:    previous-report" in rendered
    assert "Report:    current-report" in rendered
    assert "Healthy -> Warning" in rendered
    assert "100/100 -> 50/100 (-50)" in rendered
    assert "Attention: 0 -> 1 (+1)" in rendered


def test_human_renderer_renders_changed_finding() -> None:
    rendered = render_comparison_human(
        changed_comparison(),
    )

    assert "~ [system] Memory (system.memory)" in rendered
    assert "Type: Changed" in rendered
    assert (
        "Before: Healthy — Memory usage is healthy"
        in rendered
    )
    assert (
        "After:  Warning — Memory usage is elevated"
        in rendered
    )


def test_human_renderer_handles_no_differences() -> None:
    value = healthy_finding()

    comparison = OperationsComparison(
        previous=report(
            "previous-report",
            "2026-08-03T21:00:00Z",
            value,
        ),
        current=report(
            "current-report",
            "2026-08-03T22:00:00Z",
            value,
        ),
    )

    rendered = render_comparison_human(comparison)

    assert "Differences: 0" in rendered
    assert rendered.endswith(
        "Changes\n"
        "-------\n"
        "None."
    )


def test_human_renderer_omits_unchanged_details() -> None:
    value = healthy_finding()

    comparison = OperationsComparison(
        previous=report(
            "previous-report",
            "2026-08-03T21:00:00Z",
            value,
        ),
        current=report(
            "current-report",
            "2026-08-03T22:00:00Z",
            value,
        ),
        changes=(
            OperationsFindingChange(
                section="system",
                change_type="unchanged",
                before=value,
                after=value,
            ),
        ),
    )

    rendered = render_comparison_human(comparison)

    assert "Differences: 0" in rendered
    assert "system.memory" not in rendered


def test_json_renderer_matches_comparison_contract() -> None:
    comparison = changed_comparison()

    payload = json.loads(
        render_comparison_json(comparison)
    )

    assert payload == comparison.to_dict()
    assert payload["summary"]["score_delta"] == -50
    assert payload["summary"]["difference_count"] == 1


@pytest.mark.parametrize(
    "renderer",
    (
        render_comparison_human,
        render_comparison_json,
    ),
)
def test_renderers_validate_comparison(
    renderer,
) -> None:
    with pytest.raises(
        OperationsModelError,
        match="comparison must be an OperationsComparison",
    ):
        renderer(object())
