"""End-to-end cleanup workflow orchestration for Project Atlas."""

from __future__ import annotations

from atlas.cleanup.default_executor import DefaultCleanupExecutor
from atlas.cleanup.execution_models import (
    CleanupExecutionMode,
    CleanupExecutionReport,
)
from atlas.cleanup.execution_service import CleanupExecutionService
from atlas.cleanup.executor import (
    CleanupExecutionError,
    CleanupExecutionSummary,
    CleanupExecutor,
)
from atlas.cleanup.scan_models import CleanupScanReport
from atlas.cleanup.scanner import CleanupScanner
from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
)
from atlas.media.provider import MediaProvider


class CleanupWorkflowService:
    """Coordinate provider enumeration, scanning, planning, and execution."""

    def __init__(
        self,
        *,
        scanner: CleanupScanner | None = None,
        planner: CleanupExecutionService | None = None,
        executor: CleanupExecutor | None = None,
    ) -> None:
        """Initialize the cleanup workflow collaborators.

        When no executor is supplied, a provider-bound
        ``DefaultCleanupExecutor`` is created for each workflow execution.
        """

        self._scanner = scanner or CleanupScanner()
        self._planner = planner or CleanupExecutionService()
        self._executor = executor

    def execute(
        self,
        provider: MediaProvider,
        *,
        page_size: int = 200,
        mode: CleanupExecutionMode | str = (
            CleanupExecutionMode.DRY_RUN
        ),
    ) -> CleanupExecutionSummary:
        """Run the complete cleanup workflow for one media provider."""

        provider_name = self._provider_name(provider)
        self._validate_page_size(page_size)

        capabilities = self._provider_capabilities(
            provider,
        )

        if not capabilities.supports(
            ProviderCapability.LIST_MEDIA
        ):
            raise CleanupExecutionError(
                f"{provider_name} does not support media listing"
            )

        list_media_item_ids = getattr(
            provider,
            "list_media_item_ids",
            None,
        )

        if not callable(list_media_item_ids):
            raise CleanupExecutionError(
                "provider declares media listing support "
                "but does not implement list_media_item_ids"
            )

        item_ids = list_media_item_ids(
            page_size=page_size,
        )

        scan_report = self._scanner.scan(
            provider_name,
            item_ids,
        )

        if not isinstance(scan_report, CleanupScanReport):
            raise CleanupExecutionError(
                "scanner must return a CleanupScanReport"
            )

        execution_report = self._planner.plan(
            scan_report,
            mode=mode,
        )

        if not isinstance(
            execution_report,
            CleanupExecutionReport,
        ):
            raise CleanupExecutionError(
                "planner must return a CleanupExecutionReport"
            )

        executor = self._executor or DefaultCleanupExecutor(
            provider=provider,
        )

        summary = executor.execute(
            execution_report,
        )

        if not isinstance(summary, CleanupExecutionSummary):
            raise CleanupExecutionError(
                "executor must return a CleanupExecutionSummary"
            )

        return summary

    @staticmethod
    def _provider_name(
        provider: MediaProvider,
    ) -> str:
        """Return a normalized provider name."""

        try:
            name = provider.name
        except (AttributeError, TypeError) as exc:
            raise CleanupExecutionError(
                "provider must define a name"
            ) from exc

        if not isinstance(name, str) or not name.strip():
            raise CleanupExecutionError(
                "provider name is required"
            )

        return name.strip().lower()

    @staticmethod
    def _provider_capabilities(
        provider: MediaProvider,
    ) -> ProviderCapabilities:
        """Return and validate the provider capability contract."""

        get_capabilities = getattr(
            provider,
            "get_capabilities",
            None,
        )

        if not callable(get_capabilities):
            raise CleanupExecutionError(
                "provider must implement get_capabilities"
            )

        capabilities = get_capabilities()

        if not isinstance(
            capabilities,
            ProviderCapabilities,
        ):
            raise CleanupExecutionError(
                "provider must return ProviderCapabilities"
            )

        return capabilities

    @staticmethod
    def _validate_page_size(
        page_size: int,
    ) -> None:
        """Validate the provider enumeration page size."""

        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size <= 0
        ):
            raise CleanupExecutionError(
                "page_size must be a positive integer"
            )
