"""Cleanup planning service for Project Atlas."""

from __future__ import annotations

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
)
from atlas.retention.service import RetentionService


class CleanupService:
    """Translate retention decisions into cleanup recommendations."""

    def __init__(
        self,
        retention_service: RetentionService | None = None,
    ) -> None:
        self._retention_service = (
            retention_service
            if retention_service is not None
            else RetentionService()
        )

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> CleanupDecision:
        """Evaluate one media item for cleanup."""

        retention = self._retention_service.evaluate(
            provider,
            item_id,
        )

        action = (
            CleanupAction.DELETE
            if retention.eligible
            else CleanupAction.KEEP
        )

        return CleanupDecision(
            provider=retention.provider,
            item_id=retention.item_id,
            action=action,
            retention=retention,
        )
