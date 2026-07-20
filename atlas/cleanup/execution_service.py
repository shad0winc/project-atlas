"""Dry-run cleanup execution planning for Project Atlas."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from atlas.cleanup.execution_models import (
    CleanupExecutionItem,
    CleanupExecutionMode,
    CleanupExecutionReport,
    CleanupExecutionStatus,
)
from atlas.cleanup.models import (
    CleanupAction,
    CleanupError,
)
from atlas.cleanup.scan_models import CleanupScanReport


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


class CleanupExecutionService:
    """Convert cleanup scans into non-destructive execution plans."""

    def __init__(
        self,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._clock = clock or _utc_now

    def plan(
        self,
        scan: CleanupScanReport,
        *,
        mode: CleanupExecutionMode | str = (
            CleanupExecutionMode.DRY_RUN
        ),
    ) -> CleanupExecutionReport:
        """Create a dry-run execution plan from one cleanup scan."""

        if not isinstance(scan, CleanupScanReport):
            raise CleanupError(
                "scan must be a CleanupScanReport"
            )

        try:
            normalized_mode = (
                mode
                if isinstance(mode, CleanupExecutionMode)
                else CleanupExecutionMode(mode)
            )
        except (TypeError, ValueError) as exc:
            raise CleanupError(
                f"invalid cleanup execution mode: {mode}"
            ) from exc

        if normalized_mode is not CleanupExecutionMode.DRY_RUN:
            raise CleanupError(
                "only dry-run cleanup execution is supported"
            )

        planned_at = self._now()

        items = tuple(
            CleanupExecutionItem(
                provider=decision.provider,
                item_id=decision.item_id,
                decision=decision,
                mode=normalized_mode,
                status=(
                    CleanupExecutionStatus.PLANNED
                    if decision.action is CleanupAction.DELETE
                    else CleanupExecutionStatus.SKIPPED
                ),
                modified=False,
                planned_at=planned_at,
            )
            for decision in scan.decisions
        )

        return CleanupExecutionReport(
            provider=scan.provider,
            items=items,
            mode=normalized_mode,
            created_at=planned_at,
        )

    def _now(self) -> datetime:
        """Return a validated timezone-aware UTC timestamp."""

        value = self._clock()

        if not isinstance(value, datetime):
            raise CleanupError(
                "execution clock must return a datetime"
            )

        if value.tzinfo is None or value.utcoffset() is None:
            raise CleanupError(
                "execution clock must return a "
                "timezone-aware datetime"
            )

        return value.astimezone(timezone.utc)
