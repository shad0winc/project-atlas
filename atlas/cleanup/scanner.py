"""Provider-neutral cleanup library scanner."""

from __future__ import annotations

from collections.abc import Iterable

from atlas.cleanup.models import CleanupDecision, CleanupError
from atlas.cleanup.scan_models import CleanupScanReport
from atlas.cleanup.service import CleanupService


class CleanupScanner:
    """Evaluate a collection of provider item identifiers."""

    def __init__(
        self,
        cleanup_service: CleanupService | None = None,
    ) -> None:
        self._cleanup_service = (
            cleanup_service
            if cleanup_service is not None
            else CleanupService()
        )

    def scan(
        self,
        provider: str,
        item_ids: Iterable[str],
    ) -> CleanupScanReport:
        """Evaluate all item identifiers for one provider."""

        if not isinstance(provider, str):
            raise CleanupError("provider must be a string")

        normalized_provider = provider.strip().lower()

        if not normalized_provider:
            raise CleanupError("provider must not be empty")

        try:
            iterator = iter(item_ids)
        except TypeError as exc:
            raise CleanupError(
                "item_ids must be iterable"
            ) from exc

        decisions: list[CleanupDecision] = []
        seen: set[str] = set()

        for raw_item_id in iterator:
            if not isinstance(raw_item_id, str):
                raise CleanupError(
                    "item IDs must be strings"
                )

            item_id = raw_item_id.strip().lower()

            if not item_id:
                raise CleanupError(
                    "item IDs must not be empty"
                )

            if item_id in seen:
                raise CleanupError(
                    f"duplicate item ID: {item_id}"
                )

            seen.add(item_id)

            decision = self._cleanup_service.evaluate(
                normalized_provider,
                item_id,
            )

            decisions.append(decision)

        return CleanupScanReport(
            provider=normalized_provider,
            decisions=tuple(decisions),
        )
