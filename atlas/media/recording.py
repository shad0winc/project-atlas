"""Safe in-memory media provider for Project Atlas."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone

from atlas.media.provider import (
    MediaItem,
    MediaProviderError,
    ProviderMutationResult,
    ProviderOperation,
)


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


class RecordingMediaProvider:
    """Record provider operations without modifying external media.

    This provider is intended for tests and safe execution validation. Delete
    requests are stored in memory and returned as successful normalized
    mutation results. No HTTP, filesystem, or external provider operation is
    performed.
    """

    def __init__(
        self,
        name: str,
        *,
        items: Mapping[str, MediaItem] | None = None,
        clock: Clock | None = None,
    ) -> None:
        """Initialize the recording provider.

        Args:
            name: Provider name represented by this recording provider.
            items: Optional media items available through ``get_item``.
            clock: Optional timezone-aware datetime provider.

        Raises:
            MediaProviderError: If the provider name or seeded items are
                invalid.
        """

        self._name = _required_text(
            name,
            "provider name",
        ).lower()

        self._clock = clock or _utc_now
        self._items: dict[str, MediaItem] = {}
        self._requests: list[ProviderMutationResult] = []

        for item_id, item in dict(items or {}).items():
            if not isinstance(item, MediaItem):
                raise MediaProviderError(
                    "recording provider items must be MediaItem instances"
                )

            normalized_id = _required_text(
                item_id,
                "item ID",
            )

            if item.provider.strip().lower() != self._name:
                raise MediaProviderError(
                    "media item provider does not match "
                    "recording provider"
                )

            if item.item_id != normalized_id:
                raise MediaProviderError(
                    "media item ID does not match mapping key"
                )

            self._items[normalized_id] = item

    @property
    def name(self) -> str:
        """Return the normalized provider name."""

        return self._name

    @property
    def requests(self) -> tuple[ProviderMutationResult, ...]:
        """Return recorded mutation requests in execution order."""

        return tuple(self._requests)

    def get_item(
        self,
        item_id: str,
    ) -> MediaItem:
        """Return one seeded media item."""

        normalized_id = _required_text(
            item_id,
            "item_id",
        )

        try:
            return self._items[normalized_id]
        except KeyError as exc:
            raise MediaProviderError(
                f"media item not found: {normalized_id}"
            ) from exc

    def preview_delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        """Record a deletion preview without modifying media."""

        normalized_id = _required_text(
            item_id,
            "item_id",
        )

        executed_at = _timestamp(
            self._now()
        )

        result = ProviderMutationResult(
            provider=self.name,
            operation=ProviderOperation.DELETE,
            item_id=normalized_id,
            success=True,
            message=(
                "Deletion preview recorded; "
                "no media was modified"
            ),
            executed_at=executed_at,
        )

        self._requests.append(result)

        return result

    def _now(self) -> datetime:
        """Return a validated timezone-aware UTC datetime."""

        value = self._clock()

        if not isinstance(value, datetime):
            raise MediaProviderError(
                "recording provider clock must return a datetime"
            )

        if value.tzinfo is None or value.utcoffset() is None:
            raise MediaProviderError(
                "recording provider clock must return a "
                "timezone-aware datetime"
            )

        return value.astimezone(timezone.utc)


def _required_text(
    value: object,
    field_name: str,
) -> str:
    """Return a stripped, non-empty string."""

    if not isinstance(value, str) or not value.strip():
        raise MediaProviderError(
            f"{field_name} is required"
        )

    return value.strip()


def _timestamp(
    value: datetime,
) -> str:
    """Serialize a timezone-aware datetime in UTC."""

    return (
        value.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
