"""Tests for cleanup execution-history queries."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from atlas.cleanup.execution_events import (
    CleanupExecutionEvent,
    CleanupExecutionEventStatus,
)
from atlas.cleanup.execution_models import (
    CleanupExecutionMode,
)
from atlas.cleanup.history_models import (
    CleanupHistoryEntry,
    CleanupHistoryError,
)
from atlas.cleanup.history_service import (
    CleanupHistoryService,
)
from atlas.cleanup.history_store import (
    CleanupHistoryStore,
)
from atlas.cleanup.models import CleanupAction


EXECUTION_ID_1 = "cln_0123456789abcdef0123456789abcdef"
EXECUTION_ID_2 = "cln_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
EXECUTION_ID_3 = "cln_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

EARLY = datetime(
    2026,
    7,
    24,
    12,
    0,
    tzinfo=timezone.utc,
)

MIDDLE = datetime(
    2026,
    7,
    24,
    13,
    0,
    tzinfo=timezone.utc,
)

LATE = datetime(
    2026,
    7,
    24,
    14,
    0,
    tzinfo=timezone.utc,
)


def make_event(
    *,
    execution_id: str,
    provider: str,
    item_id: str,
    status: CleanupExecutionEventStatus | str,
    occurred_at: datetime,
) -> CleanupExecutionEvent:
    """Create one deterministic history event."""

    action = (
        CleanupAction.KEEP
        if status == CleanupExecutionEventStatus.SKIPPED
        or status == "skipped"
        else CleanupAction.DELETE
    )

    message = (
        "Provider unavailable"
        if status
        == CleanupExecutionEventStatus.PREVIEW_FAILED
        or status == "preview_failed"
        else "Execution completed"
    )

    return CleanupExecutionEvent(
        execution_id=execution_id,
        provider=provider,
        item_id=item_id,
        action=action,
        mode=CleanupExecutionMode.DRY_RUN,
        status=status,
        message=message,
        occurred_at=occurred_at,
    )


def make_entry(
    *,
    execution_id: str,
    provider: str,
    status: CleanupExecutionEventStatus | str,
    occurred_at: datetime,
) -> CleanupHistoryEntry:
    """Create one deterministic history entry."""

    return CleanupHistoryEntry(
        execution_id=execution_id,
        provider=provider,
        mode=CleanupExecutionMode.DRY_RUN,
        events=(
            make_event(
                execution_id=execution_id,
                provider=provider,
                item_id=f"item-{execution_id[-1]}",
                status=status,
                occurred_at=occurred_at,
            ),
        ),
    )


class FakeHistoryStore(CleanupHistoryStore):
    """Deterministic in-memory history store."""

    def __init__(
        self,
        entries: tuple[CleanupHistoryEntry, ...],
    ) -> None:
        self.entries = entries
        self.calls = 0

    def list_entries(
        self,
    ) -> tuple[CleanupHistoryEntry, ...]:
        self.calls += 1
        return self.entries


def make_entries() -> tuple[CleanupHistoryEntry, ...]:
    """Return deterministic newest-first history."""

    return (
        make_entry(
            execution_id=EXECUTION_ID_3,
            provider="jellyfin",
            status="preview_succeeded",
            occurred_at=LATE,
        ),
        make_entry(
            execution_id=EXECUTION_ID_2,
            provider="emby",
            status="preview_failed",
            occurred_at=MIDDLE,
        ),
        make_entry(
            execution_id=EXECUTION_ID_1,
            provider="jellyfin",
            status="skipped",
            occurred_at=EARLY,
        ),
    )


class CleanupHistoryServiceTests(unittest.TestCase):
    """Tests for CleanupHistoryService."""

    def test_rejects_invalid_store(self) -> None:
        with self.assertRaisesRegex(
            CleanupHistoryError,
            "store must be a CleanupHistoryStore",
        ):
            CleanupHistoryService(object())

    def test_exposes_store(self) -> None:
        store = FakeHistoryStore(())

        service = CleanupHistoryService(store)

        self.assertIs(service.store, store)

    def test_lists_all_entries(self) -> None:
        store = FakeHistoryStore(make_entries())
        service = CleanupHistoryService(store)

        entries = service.list()

        self.assertEqual(entries, make_entries())
        self.assertEqual(store.calls, 1)

    def test_limits_to_last_entries(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(make_entries())
        )

        entries = service.list(last=2)

        self.assertEqual(
            tuple(
                entry.execution_id
                for entry in entries
            ),
            (
                EXECUTION_ID_3,
                EXECUTION_ID_2,
            ),
        )

    def test_filters_by_provider(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(make_entries())
        )

        entries = service.list(
            provider=" JELLYFIN "
        )

        self.assertEqual(
            tuple(
                entry.execution_id
                for entry in entries
            ),
            (
                EXECUTION_ID_3,
                EXECUTION_ID_1,
            ),
        )

    def test_filters_entries_with_failures(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(make_entries())
        )

        entries = service.list(
            has_failures=True
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0].execution_id,
            EXECUTION_ID_2,
        )

    def test_filters_entries_without_failures(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(make_entries())
        )

        entries = service.list(
            has_failures=False
        )

        self.assertEqual(
            tuple(
                entry.execution_id
                for entry in entries
            ),
            (
                EXECUTION_ID_3,
                EXECUTION_ID_1,
            ),
        )

    def test_applies_filters_before_limit(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(make_entries())
        )

        entries = service.list(
            last=1,
            provider="jellyfin",
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0].execution_id,
            EXECUTION_ID_3,
        )

    def test_get_returns_matching_entry(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(make_entries())
        )

        entry = service.get(
            f" {EXECUTION_ID_2.upper()} "
        )

        self.assertIsNotNone(entry)
        self.assertEqual(
            entry.execution_id,
            EXECUTION_ID_2,
        )

    def test_get_returns_none_when_not_found(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(make_entries())
        )

        entry = service.get(
            "cln_cccccccccccccccccccccccccccccccc"
        )

        self.assertIsNone(entry)

    def test_rejects_invalid_execution_id(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(())
        )

        with self.assertRaisesRegex(
            CleanupHistoryError,
            "execution_id must match "
            "cln_<32 lowercase hex characters>",
        ):
            service.get("invalid")

    def test_rejects_invalid_last_type(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(())
        )

        for value in (
            True,
            "10",
            1.5,
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    CleanupHistoryError,
                    "last must be an integer",
                ):
                    service.list(last=value)

    def test_rejects_non_positive_last(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(())
        )

        for value in (
            0,
            -1,
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    CleanupHistoryError,
                    "last must be greater than zero",
                ):
                    service.list(last=value)

    def test_rejects_invalid_provider_type(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(())
        )

        with self.assertRaisesRegex(
            CleanupHistoryError,
            "provider must be a string",
        ):
            service.list(provider=123)

    def test_rejects_empty_provider(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(())
        )

        with self.assertRaisesRegex(
            CleanupHistoryError,
            "provider must not be empty",
        ):
            service.list(provider=" ")

    def test_rejects_invalid_failure_filter(self) -> None:
        service = CleanupHistoryService(
            FakeHistoryStore(())
        )

        with self.assertRaisesRegex(
            CleanupHistoryError,
            "has_failures must be a boolean",
        ):
            service.list(has_failures="yes")


if __name__ == "__main__":
    unittest.main()
