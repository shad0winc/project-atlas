"""Operations report aggregation service for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field

from .collectors import OperationsCollector
from .context import (
    HostOperationsContextProvider,
    OperationsContext,
    OperationsContextProvider,
)
from .models import (
    OperationFinding,
    OperationsReport,
    OperationsSection,
    OperationsSectionId,
    OperationsSeverity,
    OperationsStatus,
)


class OperationsServiceError(ValueError):
    """Raised when the Operations aggregation contract is invalid."""


_SECTION_ORDER = {
    section_id: index
    for index, section_id in enumerate(OperationsSectionId)
}


@dataclass(frozen=True, slots=True)
class OperationsService:
    """Aggregate collector sections into one Operations report."""

    collectors: tuple[OperationsCollector, ...]
    context_provider: OperationsContextProvider = field(
        default_factory=HostOperationsContextProvider,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.collectors, tuple):
            raise OperationsServiceError(
                "collectors must be a tuple",
            )

        if not callable(
            getattr(self.context_provider, "context", None)
        ):
            raise OperationsServiceError(
                "context_provider must define context()",
            )

        for index, collector in enumerate(self.collectors):
            if not isinstance(collector, OperationsCollector):
                raise OperationsServiceError(
                    f"collectors[{index}] must be an "
                    "OperationsCollector",
                )

        section_ids = [
            collector.section_id
            for collector in self.collectors
        ]

        if len(section_ids) != len(set(section_ids)):
            raise OperationsServiceError(
                "collectors must have unique section identifiers",
            )

        ordered = tuple(
            sorted(
                self.collectors,
                key=lambda collector: (
                    _SECTION_ORDER[collector.section_id],
                    collector.name.casefold(),
                ),
            )
        )

        object.__setattr__(
            self,
            "collectors",
            ordered,
        )

    def collect(
        self,
        *,
        report_id: str | None = None,
        hostname: str | None = None,
        atlas_version: str | None = None,
        git_commit: str | None = None,
        generated_at: str | None = None,
    ) -> OperationsReport:
        """Execute collectors and return one normalized report."""

        context = self._resolve_context(
            report_id=report_id,
            hostname=hostname,
            atlas_version=atlas_version,
            git_commit=git_commit,
            generated_at=generated_at,
        )

        sections = tuple(
            self._collect_section(collector)
            for collector in self.collectors
        )

        return OperationsReport(
            report_id=context.report_id,
            hostname=context.hostname,
            atlas_version=context.atlas_version,
            git_commit=context.git_commit,
            sections=sections,
            generated_at=context.generated_at,
        )

    def _resolve_context(
        self,
        *,
        report_id: str | None,
        hostname: str | None,
        atlas_version: str | None,
        git_commit: str | None,
        generated_at: str | None,
    ) -> OperationsContext:
        explicit_values = {
            "hostname": hostname,
            "atlas_version": atlas_version,
            "git_commit": git_commit,
            "generated_at": generated_at,
        }

        provided = {
            name
            for name, value in explicit_values.items()
            if value is not None
        }

        if provided and len(provided) != len(explicit_values):
            missing = sorted(
                set(explicit_values) - provided,
            )

            raise OperationsServiceError(
                "explicit runtime metadata must provide all of "
                "hostname, atlas_version, git_commit, and "
                "generated_at; missing: "
                + ", ".join(missing),
            )

        if provided:
            return OperationsContext(
                report_id=report_id or "operations-report",
                hostname=hostname,
                atlas_version=atlas_version,
                git_commit=git_commit,
                generated_at=generated_at,
            )

        try:
            return self.context_provider.context(
                report_id=report_id or "operations-report",
            )
        except Exception as exc:
            if isinstance(exc, OperationsServiceError):
                raise

            raise OperationsServiceError(
                "Operations runtime context collection failed: "
                f"{str(exc).strip() or exc.__class__.__name__}",
            ) from exc

    def _collect_section(
        self,
        collector: OperationsCollector,
    ) -> OperationsSection:
        try:
            return collector.collect_checked()
        except Exception as exc:
            return _collector_failure_section(
                collector=collector,
                error=exc,
            )


def _collector_failure_section(
    *,
    collector: OperationsCollector,
    error: Exception,
) -> OperationsSection:
    error_message = (
        str(error).strip()
        or error.__class__.__name__
    )

    finding = OperationFinding(
        identifier=(
            "operations.collector."
            f"{collector.section_id.value}"
        ),
        name=f"{collector.name} Collector",
        status=OperationsStatus.UNKNOWN,
        severity=OperationsSeverity.INFO,
        message=(
            f"{collector.name} Operations collection failed"
        ),
        recommendation=(
            "Review the collector error and restore its "
            "data source before relying on this section."
        ),
        metadata={
            "collector": collector.__class__.__name__,
            "error": error_message,
            "section": collector.section_id.value,
        },
    )

    return OperationsSection(
        identifier=collector.section_id,
        name=collector.name,
        description=collector.description,
        findings=(finding,),
    )
