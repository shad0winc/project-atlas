"""Tests for the Atlas Operations aggregation service."""

from dataclasses import FrozenInstanceError, dataclass, field

import pytest

from atlas.operations import (
    OperationFinding,
    OperationsContext,
    OperationsReport,
    OperationsSection,
    OperationsSectionId,
    OperationsService,
    OperationsServiceError,
    OperationsStatus,
)
from atlas.operations.collectors import OperationsCollector


class FakeOperationsContextProvider:
    """Deterministic runtime context for service tests."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def context(
        self,
        *,
        report_id: str = "operations-report",
    ) -> OperationsContext:
        self.calls.append(report_id)

        return OperationsContext(
            report_id=report_id,
            hostname=" Docker ",
            atlas_version=" 0.9.0-rc.1 ",
            git_commit="087D4322",
            generated_at="2026-08-03T15:00:00-04:00",
        )


def healthy_section(
    section_id: OperationsSectionId,
    name: str,
) -> OperationsSection:
    return OperationsSection(
        identifier=section_id,
        name=name,
        findings=(
            OperationFinding(
                identifier=(
                    f"{section_id.value}.availability"
                ),
                name=f"{name} Availability",
                status="healthy",
                severity="info",
                message=f"{name} is available",
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class StaticCollector(OperationsCollector):
    """Collector returning one deterministic section."""

    result: OperationsSection = field(
        default_factory=lambda: healthy_section(
            OperationsSectionId.SYSTEM,
            "System",
        ),
        repr=False,
        compare=False,
    )

    def collect(self) -> OperationsSection:
        return self.result


@dataclass(frozen=True, slots=True)
class FailingCollector(OperationsCollector):
    """Collector raising one deterministic failure."""

    error_message: str = "collector unavailable"

    def collect(self) -> OperationsSection:
        raise RuntimeError(self.error_message)


def system_collector() -> StaticCollector:
    return StaticCollector(
        section_id=OperationsSectionId.SYSTEM,
        name="System",
        description="Host system checks",
        result=healthy_section(
            OperationsSectionId.SYSTEM,
            "System",
        ),
    )


def containers_collector() -> StaticCollector:
    return StaticCollector(
        section_id=OperationsSectionId.CONTAINERS,
        name="Containers",
        description="Container checks",
        result=healthy_section(
            OperationsSectionId.CONTAINERS,
            "Containers",
        ),
    )


def collect_report(
    service: OperationsService,
) -> OperationsReport:
    return service.collect(
        report_id="daily-operations",
        hostname=" Docker ",
        atlas_version=" 0.9.0 ",
        git_commit="087D4322",
        generated_at="2026-08-03T15:00:00-04:00",
    )


def test_service_normalizes_collector_order() -> None:
    service = OperationsService(
        collectors=(
            containers_collector(),
            system_collector(),
        ),
    )

    assert tuple(
        collector.section_id
        for collector in service.collectors
    ) == (
        OperationsSectionId.SYSTEM,
        OperationsSectionId.CONTAINERS,
    )


def test_service_builds_operations_report() -> None:
    report = collect_report(
        OperationsService(
            collectors=(
                system_collector(),
                containers_collector(),
            ),
        )
    )

    assert isinstance(report, OperationsReport)
    assert report.report_id == "daily-operations"
    assert report.hostname == "docker"
    assert report.atlas_version == "0.9.0"
    assert report.git_commit == "087d4322"
    assert report.generated_at == "2026-08-03T19:00:00Z"

    assert tuple(
        section.identifier
        for section in report.sections
    ) == (
        OperationsSectionId.SYSTEM,
        OperationsSectionId.CONTAINERS,
    )


def test_service_report_is_healthy_when_sections_are_healthy() -> None:
    report = collect_report(
        OperationsService(
            collectors=(
                system_collector(),
                containers_collector(),
            ),
        )
    )

    assert report.status is OperationsStatus.HEALTHY
    assert report.score == 100
    assert report.summary.section_count == 2
    assert report.summary.finding_count == 2


def test_service_executes_each_collector_once() -> None:
    calls: list[str] = []

    @dataclass(frozen=True, slots=True)
    class RecordingCollector(OperationsCollector):
        result: OperationsSection = field(
            default_factory=lambda: healthy_section(
                OperationsSectionId.SYSTEM,
                "System",
            ),
            repr=False,
            compare=False,
        )

        def collect(self) -> OperationsSection:
            calls.append(self.section_id.value)
            return self.result

    service = OperationsService(
        collectors=(
            RecordingCollector(
                section_id=OperationsSectionId.CONTAINERS,
                name="Containers",
                result=healthy_section(
                    OperationsSectionId.CONTAINERS,
                    "Containers",
                ),
            ),
            RecordingCollector(
                section_id=OperationsSectionId.SYSTEM,
                name="System",
                result=healthy_section(
                    OperationsSectionId.SYSTEM,
                    "System",
                ),
            ),
        ),
    )

    collect_report(service)

    assert calls == [
        "system",
        "containers",
    ]


def test_collector_failure_is_isolated() -> None:
    service = OperationsService(
        collectors=(
            system_collector(),
            FailingCollector(
                section_id=OperationsSectionId.CONTAINERS,
                name="Containers",
                description="Container checks",
                error_message="Docker unavailable",
            ),
        ),
    )

    report = collect_report(service)

    assert len(report.sections) == 2
    assert report.sections[0].status is OperationsStatus.HEALTHY
    assert report.sections[1].status is OperationsStatus.UNKNOWN

    failure = report.sections[1].findings[0]

    assert failure.identifier == (
        "operations.collector.containers"
    )
    assert failure.status is OperationsStatus.UNKNOWN
    assert failure.metadata == {
        "collector": "FailingCollector",
        "error": "containers collector failed: Docker unavailable",
        "section": "containers",
    }


def test_multiple_collector_failures_do_not_abort_report() -> None:
    service = OperationsService(
        collectors=(
            FailingCollector(
                section_id=OperationsSectionId.SYSTEM,
                name="System",
                error_message="system unavailable",
            ),
            FailingCollector(
                section_id=OperationsSectionId.CONTAINERS,
                name="Containers",
                error_message="docker unavailable",
            ),
        ),
    )

    report = collect_report(service)

    assert tuple(
        section.status
        for section in report.sections
    ) == (
        OperationsStatus.UNKNOWN,
        OperationsStatus.UNKNOWN,
    )

    assert report.status is OperationsStatus.UNKNOWN
    assert report.summary.unknown_count == 2


def test_service_allows_empty_collector_set() -> None:
    report = collect_report(
        OperationsService(
            collectors=(),
        )
    )

    assert report.sections == ()
    assert report.status is OperationsStatus.UNKNOWN
    assert report.score == 0


def test_service_rejects_duplicate_section_collectors() -> None:
    with pytest.raises(
        OperationsServiceError,
        match="unique section identifiers",
    ):
        OperationsService(
            collectors=(
                system_collector(),
                system_collector(),
            ),
        )


def test_service_rejects_non_tuple_collectors() -> None:
    with pytest.raises(
        OperationsServiceError,
        match="collectors must be a tuple",
    ):
        OperationsService(
            collectors=[  # type: ignore[arg-type]
                system_collector(),
            ],
        )


def test_service_rejects_invalid_collector_child() -> None:
    with pytest.raises(
        OperationsServiceError,
        match=r"collectors\[0\] must be an OperationsCollector",
    ):
        OperationsService(
            collectors=(
                object(),  # type: ignore[arg-type]
            ),
        )


def test_service_preserves_report_validation() -> None:
    service = OperationsService(
        collectors=(
            system_collector(),
        ),
    )

    with pytest.raises(Exception):
        service.collect(
            report_id="daily",
            hostname="docker",
            atlas_version="0.9.0",
            git_commit="invalid",
            generated_at="2026-08-03T19:00:00Z",
        )


def test_service_is_immutable() -> None:
    service = OperationsService(
        collectors=(
            system_collector(),
        ),
    )

    with pytest.raises(FrozenInstanceError):
        service.collectors = ()  # type: ignore[misc]


def test_public_service_exports() -> None:
    from atlas import operations

    assert operations.OperationsService is OperationsService
    assert (
        operations.OperationsServiceError
        is OperationsServiceError
    )


def test_service_collects_context_automatically() -> None:
    context_provider = FakeOperationsContextProvider()

    service = OperationsService(
        collectors=(
            system_collector(),
            containers_collector(),
        ),
        context_provider=context_provider,
    )

    report = service.collect()

    assert report.report_id == "operations-report"
    assert report.hostname == "docker"
    assert report.atlas_version == "0.9.0-rc.1"
    assert report.git_commit == "087d4322"
    assert report.generated_at == "2026-08-03T19:00:00Z"
    assert context_provider.calls == [
        "operations-report",
    ]


def test_service_passes_report_id_override_to_context() -> None:
    context_provider = FakeOperationsContextProvider()

    report = OperationsService(
        collectors=(
            system_collector(),
        ),
        context_provider=context_provider,
    ).collect(
        report_id="daily-operations",
    )

    assert report.report_id == "daily-operations"
    assert context_provider.calls == [
        "daily-operations",
    ]


def test_explicit_metadata_bypasses_context_provider() -> None:
    class ForbiddenContextProvider:
        def context(self, *, report_id: str = "operations-report"):
            raise AssertionError(
                "context provider must not be called",
            )

    report = OperationsService(
        collectors=(
            system_collector(),
        ),
        context_provider=ForbiddenContextProvider(),
    ).collect(
        report_id="explicit-report",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="087d4322",
        generated_at="2026-08-03T19:00:00Z",
    )

    assert report.report_id == "explicit-report"
    assert report.hostname == "docker"


def test_explicit_metadata_uses_default_report_id() -> None:
    class ForbiddenContextProvider:
        def context(self, *, report_id: str = "operations-report"):
            raise AssertionError(
                "context provider must not be called",
            )

    report = OperationsService(
        collectors=(),
        context_provider=ForbiddenContextProvider(),
    ).collect(
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="087d4322",
        generated_at="2026-08-03T19:00:00Z",
    )

    assert report.report_id == "operations-report"


@pytest.mark.parametrize(
    "metadata",
    (
        {
            "hostname": "docker",
        },
        {
            "atlas_version": "0.9.0-rc.1",
            "git_commit": "087d4322",
        },
        {
            "hostname": "docker",
            "atlas_version": "0.9.0-rc.1",
            "git_commit": "087d4322",
        },
        {
            "hostname": "docker",
            "generated_at": "2026-08-03T19:00:00Z",
        },
    ),
)
def test_service_rejects_partial_explicit_metadata(
    metadata: dict[str, str],
) -> None:
    with pytest.raises(
        OperationsServiceError,
        match="explicit runtime metadata must provide all",
    ):
        OperationsService(
            collectors=(),
            context_provider=FakeOperationsContextProvider(),
        ).collect(
            **metadata,
        )


def test_service_wraps_context_provider_failure() -> None:
    class FailingContextProvider:
        def context(
            self,
            *,
            report_id: str = "operations-report",
        ):
            raise RuntimeError("context unavailable")

    service = OperationsService(
        collectors=(),
        context_provider=FailingContextProvider(),
    )

    with pytest.raises(
        OperationsServiceError,
        match=(
            "Operations runtime context collection failed: "
            "context unavailable"
        ),
    ):
        service.collect()


def test_service_acquires_context_once() -> None:
    context_provider = FakeOperationsContextProvider()

    service = OperationsService(
        collectors=(
            system_collector(),
            containers_collector(),
        ),
        context_provider=context_provider,
    )

    service.collect()

    assert context_provider.calls == [
        "operations-report",
    ]


def test_service_rejects_invalid_context_provider() -> None:
    with pytest.raises(
        OperationsServiceError,
        match=r"context_provider must define context\(\)",
    ):
        OperationsService(
            collectors=(),
            context_provider=object(),  # type: ignore[arg-type]
        )
