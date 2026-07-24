"""Cleanup execution-history query service for Project Atlas."""

from __future__ import annotations

from atlas.cleanup.execution_identity import (
    normalize_execution_id,
)
from atlas.cleanup.history_models import (
    CleanupHistoryEntry,
    CleanupHistoryError,
)
from atlas.cleanup.history_store import (
    CleanupHistoryStore,
)


class CleanupHistoryService:
    """Query normalized cleanup execution history."""

    def __init__(
        self,
        store: CleanupHistoryStore,
    ) -> None:
        """Initialize the history service."""

        if not isinstance(store, CleanupHistoryStore):
            raise CleanupHistoryError(
                "store must be a CleanupHistoryStore"
            )

        self._store = store

    @property
    def store(self) -> CleanupHistoryStore:
        """Return the configured history store."""

        return self._store

    def list(
        self,
        *,
        last: int | None = None,
        provider: str | None = None,
        has_failures: bool | None = None,
    ) -> tuple[CleanupHistoryEntry, ...]:
        """Return cleanup history matching optional filters."""

        normalized_last = _normalize_last(last)
        normalized_provider = _normalize_provider(provider)
        normalized_has_failures = _normalize_has_failures(
            has_failures
        )

        entries = self._store.list_entries()

        if normalized_provider is not None:
            entries = tuple(
                entry
                for entry in entries
                if entry.provider == normalized_provider
            )

        if normalized_has_failures is not None:
            entries = tuple(
                entry
                for entry in entries
                if (
                    entry.has_failures
                    is normalized_has_failures
                )
            )

        if normalized_last is not None:
            entries = entries[:normalized_last]

        return entries

    def get(
        self,
        execution_id: str,
    ) -> CleanupHistoryEntry | None:
        """Return one execution-history entry by ID."""

        try:
            normalized_execution_id = normalize_execution_id(
                execution_id
            )
        except ValueError as exc:
            raise CleanupHistoryError(str(exc)) from exc

        for entry in self._store.list_entries():
            if entry.execution_id == normalized_execution_id:
                return entry

        return None


def _normalize_last(
    value: int | None,
) -> int | None:
    """Normalize an optional result limit."""

    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise CleanupHistoryError(
            "last must be an integer"
        )

    if value <= 0:
        raise CleanupHistoryError(
            "last must be greater than zero"
        )

    return value


def _normalize_provider(
    value: str | None,
) -> str | None:
    """Normalize an optional provider filter."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise CleanupHistoryError(
            "provider must be a string"
        )

    normalized = value.strip().lower()

    if not normalized:
        raise CleanupHistoryError(
            "provider must not be empty"
        )

    return normalized


def _normalize_has_failures(
    value: bool | None,
) -> bool | None:
    """Normalize an optional failure-state filter."""

    if value is None:
        return None

    if not isinstance(value, bool):
        raise CleanupHistoryError(
            "has_failures must be a boolean"
        )

    return value
