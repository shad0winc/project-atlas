"""Tests for the Project Atlas Operations CLI."""

from __future__ import annotations

from io import StringIO
import json

import pytest

from atlas.operations import (
    OperationFinding,
    OperationsReport,
    OperationsSection,
)
from atlas.operations_cli import (
    build_parser,
    main,
    render_report_human,
    render_history_human,
    render_history_json,
)


def operations_report(
    *,
    status: str = "healthy",
) -> OperationsReport:
    finding = OperationFinding(
        identifier="system.hostname",
        name="Hostname",
        status=status,
        severity=(
            "info"
            if status in {"healthy", "unknown"}
            else status
        ),
        message="Hostname is available",
        recommendation=(
            None
            if status in {"healthy", "unknown"}
            else "Review the hostname source."
        ),
    )

    return OperationsReport(
        report_id="operations-report",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="087d4322",
        generated_at="2026-08-03T19:00:00Z",
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(finding,),
            ),
        ),
    )


class FakeOperationsService:
    """Deterministic service used by CLI tests."""

    def __init__(self) -> None:
        self.report_ids: list[str] = []

    def collect(
        self,
        *,
        report_id: str = "operations-report",
    ) -> OperationsReport:
        self.report_ids.append(report_id)
        return operations_report()


def test_parser_builds() -> None:
    parser = build_parser()

    assert parser.prog == "atlas operations"


def test_parser_accepts_report_command() -> None:
    args = build_parser().parse_args(
        ["report"],
    )

    assert args.command == "report"
    assert args.json is False
    assert args.report_id == "operations-report"


def test_parser_accepts_json_output() -> None:
    args = build_parser().parse_args(
        ["report", "--json"],
    )

    assert args.command == "report"
    assert args.json is True


def test_parser_accepts_report_id() -> None:
    args = build_parser().parse_args(
        [
            "report",
            "--report-id",
            "daily-operations",
        ],
    )

    assert args.report_id == "daily-operations"


def test_human_renderer_is_deterministic() -> None:
    rendered = render_report_human(
        operations_report(),
    )

    assert rendered == (
        "Atlas Operations Report\n"
        "=======================\n"
        "\n"
        "Report:      operations-report\n"
        "Generated:   2026-08-03T19:00:00Z\n"
        "Host:        docker\n"
        "Version:     0.9.0-rc.1\n"
        "Commit:      087d4322\n"
        "\n"
        "Overall\n"
        "-------\n"
        "[OK] Status: Healthy\n"
        "Score:       100/100\n"
        "Sections:    1\n"
        "Findings:    1\n"
        "Attention:   0\n"
        "\n"
        "Sections\n"
        "--------\n"
        "[OK] System\n"
        "  Status: Healthy\n"
        "  Score:  100/100\n"
        "  Findings: 1\n"
        "\n"
        "  [OK] Hostname\n"
        "       Hostname is available\n"
        "\n"
        "Attention Required\n"
        "------------------\n"
        "None."
    )


def test_main_renders_human_report() -> None:
    service = FakeOperationsService()
    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["report"],
        service_factory=lambda: service,
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert "Atlas Operations Report" in stdout.getvalue()
    assert "[OK] System" in stdout.getvalue()
    assert "Status: Healthy" in stdout.getvalue()
    assert "[OK] Hostname" in stdout.getvalue()
    assert stderr.getvalue() == ""
    assert service.report_ids == [
        "operations-report",
    ]


def test_main_renders_deterministic_json() -> None:
    service = FakeOperationsService()
    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["report", "--json"],
        service_factory=lambda: service,
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert json.loads(stdout.getvalue()) == (
        operations_report().to_dict()
    )
    assert stderr.getvalue() == ""


def test_main_passes_report_id_to_service() -> None:
    service = FakeOperationsService()

    result = main(
        [
            "report",
            "--report-id",
            "daily-operations",
        ],
        service_factory=lambda: service,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert result == 0
    assert service.report_ids == [
        "daily-operations",
    ]


def test_main_returns_one_for_service_failure() -> None:
    class FailingService:
        def collect(
            self,
            *,
            report_id: str = "operations-report",
        ):
            raise RuntimeError("collection unavailable")

    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["report"],
        service_factory=FailingService,
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "Operations report failed: "
        "collection unavailable\n"
    )


def test_main_returns_parser_exit_code_for_unknown_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        ["unknown"],
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "invalid choice" in captured.err


def test_main_returns_zero_for_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        ["--help"],
    )

    captured = capsys.readouterr()

    assert result == 0
    assert "atlas operations" in captured.out
    assert "report" in captured.out


def test_main_requires_subcommand(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main([])

    captured = capsys.readouterr()

    assert result == 2
    assert "required" in captured.err


def test_default_service_factory_contract() -> None:
    from atlas.operations_cli import (
        default_service_factory,
    )

    service = default_service_factory()

    assert tuple(
        collector.section_id.value
        for collector in service.collectors
    ) == (
        "system",
        "containers",
    )


@pytest.mark.parametrize(
    ("status", "expected_marker", "expected_label"),
    (
        ("healthy", "[OK]", "Healthy"),
        ("warning", "[!]", "Warning"),
        ("critical", "[X]", "Critical"),
        ("unknown", "[?]", "Unknown"),
    ),
)
def test_human_renderer_uses_status_markers(
    status: str,
    expected_marker: str,
    expected_label: str,
) -> None:
    rendered = render_report_human(
        operations_report(status=status),
    )

    assert (
        f"{expected_marker} Status: {expected_label}"
        in rendered
    )


def test_human_renderer_includes_recommendations() -> None:
    rendered = render_report_human(
        operations_report(status="warning"),
    )

    assert (
        "Recommendation: Review the hostname source."
        in rendered
    )


def test_human_renderer_lists_attention_findings() -> None:
    rendered = render_report_human(
        operations_report(status="critical"),
    )

    assert "Attention:   1" in rendered

    assert (
        "[X] Hostname: Hostname is available"
        in rendered
    )

    assert (
        "Recommendation: Review the hostname source."
        in rendered
    )


def test_human_renderer_handles_empty_report() -> None:
    report = OperationsReport(
        report_id="empty-report",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="087d4322",
        generated_at="2026-08-03T19:00:00Z",
        sections=(),
    )

    rendered = render_report_human(report)

    assert "[?] Status: Unknown" in rendered
    assert "Score:       0/100" in rendered
    assert "No Operations sections were collected." in rendered
    assert rendered.endswith(
        "Attention Required\n"
        "------------------\n"
        "None."
    )


def test_json_output_contract_is_unchanged() -> None:
    service = FakeOperationsService()
    stdout = StringIO()

    result = main(
        ["report", "--json"],
        service_factory=lambda: service,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0

    payload = json.loads(stdout.getvalue())

    assert payload == operations_report().to_dict()
    assert "Atlas Operations Report" not in stdout.getvalue()


def history_report(
    *,
    report_id: str,
    generated_at: str,
) -> OperationsReport:
    """Build a distinct report for history rendering tests."""

    base = operations_report()

    return OperationsReport(
        report_id=report_id,
        hostname=base.hostname,
        atlas_version=base.atlas_version,
        git_commit=base.git_commit,
        generated_at=generated_at,
        sections=base.sections,
    )


def comparison_report(
    *,
    report_id: str,
    generated_at: str,
    warning: bool,
) -> OperationsReport:
    """Build one deterministic report for comparison CLI tests."""

    finding = OperationFinding(
        identifier="system.memory",
        name="Memory",
        status="warning" if warning else "healthy",
        severity="warning" if warning else "info",
        message=(
            "Memory usage is elevated"
            if warning
            else "Memory usage is healthy"
        ),
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
                findings=(finding,),
            ),
        ),
    )


class FakeOperationsRepository:
    def __init__(self) -> None:
        self.saved: list[OperationsReport] = []
        self.latest_report = operations_report()
        self.history_limits: list[int] = []
        self.history_reports = (
            history_report(
                report_id="newest-report",
                generated_at="2026-08-03T22:00:00Z",
            ),
            history_report(
                report_id="older-report",
                generated_at="2026-08-03T21:00:00Z",
            ),
        )
        self.comparison_reports = (
            comparison_report(
                report_id="current-report",
                generated_at="2026-08-03T22:00:00Z",
                warning=True,
            ),
            comparison_report(
                report_id="previous-report",
                generated_at="2026-08-03T21:00:00Z",
                warning=False,
            ),
        )

    def save(self, report: OperationsReport):
        from pathlib import Path

        self.saved.append(report)
        return Path(
            "/tmp/operations/history/"
            "2026-08-03T19-00-00Z.json"
        )

    def latest(self) -> OperationsReport:
        return self.latest_report

    def history(
        self,
        limit: int = 25,
    ) -> tuple[OperationsReport, ...]:
        self.history_limits.append(limit)
        return self.history_reports[:limit]


def test_parser_accepts_save_command() -> None:
    args = build_parser().parse_args(["save"])

    assert args.command == "save"
    assert args.report_id == "operations-report"
    assert args.json is False


def test_parser_accepts_latest_command() -> None:
    args = build_parser().parse_args(["latest"])

    assert args.command == "latest"
    assert args.json is False


def test_main_saves_collected_report() -> None:
    service = FakeOperationsService()
    repository = FakeOperationsRepository()
    stdout = StringIO()

    result = main(
        ["save", "--report-id", "nightly"],
        service_factory=lambda: service,
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0
    assert service.report_ids == ["nightly"]
    assert repository.saved == [operations_report()]
    assert "Atlas Operations Report" in stdout.getvalue()
    assert "Saved: /tmp/operations/history/" in stdout.getvalue()


def test_main_saves_and_renders_json() -> None:
    service = FakeOperationsService()
    repository = FakeOperationsRepository()
    stdout = StringIO()

    result = main(
        ["save", "--json"],
        service_factory=lambda: service,
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0
    assert json.loads(stdout.getvalue()) == (
        operations_report().to_dict()
    )


def test_main_renders_latest_report() -> None:
    repository = FakeOperationsRepository()
    stdout = StringIO()

    result = main(
        ["latest"],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0
    assert "Atlas Operations Report" in stdout.getvalue()


def test_main_renders_latest_json() -> None:
    repository = FakeOperationsRepository()
    stdout = StringIO()

    result = main(
        ["latest", "--json"],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0
    assert json.loads(stdout.getvalue()) == (
        operations_report().to_dict()
    )


@pytest.mark.parametrize(
    ("command", "message"),
    (
        ("save", "Operations save failed"),
        ("latest", "Operations latest failed"),
    ),
)
def test_persistence_commands_normalize_failures(
    command: str,
    message: str,
) -> None:
    class BrokenRepository(FakeOperationsRepository):
        def save(self, report: OperationsReport):
            raise RuntimeError("storage unavailable")

        def latest(self) -> OperationsReport:
            raise RuntimeError("storage unavailable")

    stderr = StringIO()

    result = main(
        [command],
        service_factory=FakeOperationsService,
        repository_factory=BrokenRepository,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert result == 1
    assert message in stderr.getvalue()
    assert "storage unavailable" in stderr.getvalue()


def test_parser_accepts_history_command() -> None:
    args = build_parser().parse_args(["history"])

    assert args.command == "history"
    assert args.limit == 25
    assert args.json is False


def test_parser_accepts_history_options() -> None:
    args = build_parser().parse_args(
        [
            "history",
            "--limit",
            "10",
            "--json",
        ]
    )

    assert args.command == "history"
    assert args.limit == 10
    assert args.json is True


def test_history_human_renderer_lists_newest_first() -> None:
    repository = FakeOperationsRepository()

    rendered = render_history_human(
        repository.history_reports,
    )

    assert rendered.startswith(
        "Atlas Operations History\n"
        "========================\n"
    )
    assert "Reports: 2" in rendered
    assert rendered.index("newest-report") < rendered.index(
        "older-report"
    )
    assert "Status:    Healthy" in rendered
    assert "Score:     100/100" in rendered


def test_history_human_renderer_handles_empty_history() -> None:
    rendered = render_history_human(())

    assert rendered == (
        "Atlas Operations History\n"
        "========================\n"
        "\n"
        "Reports: 0\n"
        "\n"
        "No persisted Operations reports were found."
    )


def test_history_json_renderer_uses_wrapped_contract() -> None:
    repository = FakeOperationsRepository()

    payload = json.loads(
        render_history_json(
            repository.history_reports,
        )
    )

    assert payload == {
        "count": 2,
        "reports": [
            report.to_dict()
            for report in repository.history_reports
        ],
    }


def test_main_renders_operations_history() -> None:
    repository = FakeOperationsRepository()
    stdout = StringIO()

    result = main(
        ["history"],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0
    assert repository.history_limits == [25]
    assert "Atlas Operations History" in stdout.getvalue()
    assert "Reports: 2" in stdout.getvalue()
    assert stdout.getvalue().index(
        "newest-report"
    ) < stdout.getvalue().index(
        "older-report"
    )


def test_main_renders_operations_history_json() -> None:
    repository = FakeOperationsRepository()
    stdout = StringIO()

    result = main(
        [
            "history",
            "--limit",
            "1",
            "--json",
        ],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0
    assert repository.history_limits == [1]

    payload = json.loads(
        stdout.getvalue()
    )

    assert payload["count"] == 1
    assert tuple(
        report["report_id"]
        for report in payload["reports"]
    ) == (
        "newest-report",
    )


def test_main_renders_empty_operations_history() -> None:
    repository = FakeOperationsRepository()
    repository.history_reports = ()
    stdout = StringIO()

    result = main(
        ["history"],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0
    assert "Reports: 0" in stdout.getvalue()
    assert (
        "No persisted Operations reports were found."
        in stdout.getvalue()
    )


def test_main_normalizes_history_failure() -> None:
    class BrokenRepository(FakeOperationsRepository):
        def history(
            self,
            limit: int = 25,
        ) -> tuple[OperationsReport, ...]:
            raise RuntimeError("history unavailable")

    stderr = StringIO()

    result = main(
        ["history"],
        repository_factory=BrokenRepository,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert result == 1
    assert "Operations history failed" in stderr.getvalue()
    assert "history unavailable" in stderr.getvalue()


def test_parser_accepts_compare_command() -> None:
    args = build_parser().parse_args(["compare"])

    assert args.command == "compare"
    assert args.json is False
    assert args.include_unchanged is False


def test_parser_accepts_compare_options() -> None:
    args = build_parser().parse_args(
        [
            "compare",
            "--json",
            "--include-unchanged",
        ]
    )

    assert args.command == "compare"
    assert args.json is True
    assert args.include_unchanged is True


def test_main_renders_operations_comparison() -> None:
    repository = FakeOperationsRepository()
    repository.history_reports = repository.comparison_reports
    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["compare"],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert stderr.getvalue() == ""
    assert repository.history_limits == [2]

    rendered = stdout.getvalue()

    assert "Atlas Operations Comparison" in rendered
    assert "previous-report" in rendered
    assert "current-report" in rendered
    assert "Healthy -> Warning" in rendered
    assert "100/100 -> 50/100 (-50)" in rendered
    assert "~ [system] Memory (system.memory)" in rendered


def test_main_renders_operations_comparison_json() -> None:
    repository = FakeOperationsRepository()
    repository.history_reports = repository.comparison_reports
    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["compare", "--json"],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert stderr.getvalue() == ""
    assert repository.history_limits == [2]

    payload = json.loads(
        stdout.getvalue()
    )

    assert payload["previous"]["report_id"] == (
        "previous-report"
    )
    assert payload["current"]["report_id"] == (
        "current-report"
    )
    assert payload["summary"]["status_changed"] is True
    assert payload["summary"]["score_delta"] == -50
    assert payload["summary"]["changed_count"] == 1


def test_main_compare_can_include_unchanged() -> None:
    repository = FakeOperationsRepository()
    current = comparison_report(
        report_id="current-report",
        generated_at="2026-08-03T22:00:00Z",
        warning=False,
    )
    previous = comparison_report(
        report_id="previous-report",
        generated_at="2026-08-03T21:00:00Z",
        warning=False,
    )
    repository.history_reports = (
        current,
        previous,
    )

    stdout = StringIO()

    result = main(
        [
            "compare",
            "--json",
            "--include-unchanged",
        ],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert result == 0

    payload = json.loads(
        stdout.getvalue()
    )

    assert payload["summary"]["difference_count"] == 0
    assert payload["summary"]["unchanged_count"] == 1
    assert payload["changes"][0]["change_type"] == (
        "unchanged"
    )


def test_main_compare_requires_two_reports() -> None:
    repository = FakeOperationsRepository()
    repository.history_reports = (
        comparison_report(
            report_id="only-report",
            generated_at="2026-08-03T22:00:00Z",
            warning=False,
        ),
    )

    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["compare"],
        repository_factory=lambda: repository,
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 1
    assert stdout.getvalue() == ""
    assert repository.history_limits == [2]
    assert (
        "at least two persisted reports are required"
        in stderr.getvalue()
    )


def test_main_compare_normalizes_repository_failure() -> None:
    class BrokenRepository(FakeOperationsRepository):
        def history(
            self,
            limit: int = 25,
        ) -> tuple[OperationsReport, ...]:
            raise RuntimeError("history unavailable")

    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["compare"],
        repository_factory=BrokenRepository,
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 1
    assert stdout.getvalue() == ""
    assert "Operations comparison failed" in stderr.getvalue()
    assert "history unavailable" in stderr.getvalue()
