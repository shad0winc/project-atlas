"""Tests for cleanup execution-history models."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

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
from atlas.cleanup.models import CleanupAction


EXECUTION_ID = "cln_0123456789abcdef0123456789abcdef"

EARLY = datetime(
    2026,
    7,
    24,
    12,
    0,
    tzinfo=timezone.utc,
)

LATE = datetime(
    2026,
    7,
    24,
    12,
    1,
    tzinfo=timezone.utc,
)


def make_event(
    *,
    execution_id: str = EXECUTION_ID,
    provider: str = "jellyfin",
    item_id: str = "movie-1",
    status: CleanupExecutionEventStatus | str = (
        CleanupExecutionEventStatus.PREVIEW_SUCCEEDED
    ),
    message: str = "Preview verified",
    occurred_at: datetime = EARLY,
) -> CleanupExecutionEvent:
    """Create one deterministic history event."""

    action = (
        CleanupAction.KEEP
        if status == CleanupExecutionEventStatus.SKIPPED
        or status == "skipped"
        else CleanupAction.DELETE
    )

    return CleanupExecutionEvent(
        execution_id=execution_id,
        provider=provider,
        item_id=item_id,
        action=action,
        mode=CleanupExecutionMode.DRY_RUN,
        status=status,
        message=message,
        modified=False,
        occurred_at=occurred_at,
    )


def make_entry(
    *,
    execution_id: str = EXECUTION_ID,
    provider: str = "jellyfin",
    mode: CleanupExecutionMode = (
        CleanupExecutionMode.DRY_RUN
    ),
    events: tuple[CleanupExecutionEvent, ...] | None = None,
) -> CleanupHistoryEntry:
    """Create one deterministic history entry."""

    return CleanupHistoryEntry(
        execution_id=execution_id,
        provider=provider,
        mode=mode,
        events=(
            events
            if events is not None
            else (
                make_event(),
            )
        ),
    )


class CleanupHistoryEntryTests(unittest.TestCase):
    """Tests for CleanupHistoryEntry."""

    def test_normalizes_identity_and_provider(self) -> None:
        event = make_event(
            execution_id=EXECUTION_ID,
            provider="jellyfin",
        )

        entry = make_entry(
            execution_id=f" {EXECUTION_ID.upper()} ",
            provider=" JELLYFIN ",
            events=(event,),
        )

        self.assertEqual(
            entry.execution_id,
            EXECUTION_ID,
        )
        self.assertEqual(entry.provider, "jellyfin")
        self.assertIs(
            entry.mode,
            CleanupExecutionMode.DRY_RUN,
        )

    def test_orders_events_by_timestamp_and_item_id(
        self,
    ) -> None:
        events = (
            make_event(
                item_id="movie-3",
                occurred_at=LATE,
            ),
            make_event(
                item_id="movie-2",
                occurred_at=EARLY,
            ),
            make_event(
                item_id="movie-1",
                occurred_at=EARLY,
            ),
        )

        entry = make_entry(events=events)

        self.assertEqual(
            tuple(
                event.item_id
                for event in entry.events
            ),
            (
                "movie-1",
                "movie-2",
                "movie-3",
            ),
        )
        self.assertEqual(entry.started_at, EARLY)
        self.assertEqual(entry.completed_at, LATE)

    def test_exposes_event_counts(self) -> None:
        entry = make_entry(
            events=(
                make_event(
                    item_id="movie-1",
                    status="preview_succeeded",
                ),
                make_event(
                    item_id="movie-2",
                    status="preview_failed",
                    message="Provider unavailable",
                ),
                make_event(
                    item_id="movie-3",
                    status="skipped",
                    message="Cleanup item was not planned",
                ),
            )
        )

        self.assertEqual(entry.total, 3)
        self.assertEqual(
            entry.preview_succeeded_count,
            1,
        )
        self.assertEqual(
            entry.preview_failed_count,
            1,
        )
        self.assertEqual(entry.skipped_count, 1)
        self.assertEqual(entry.successful_count, 2)
        self.assertEqual(entry.failed_count, 1)
        self.assertEqual(entry.modified_count, 0)
        self.assertTrue(entry.has_failures)

    def test_events_for_filters_by_status(self) -> None:
        entry = make_entry(
            events=(
                make_event(
                    item_id="movie-1",
                    status="preview_succeeded",
                ),
                make_event(
                    item_id="movie-2",
                    status="preview_failed",
                    message="Provider unavailable",
                ),
                make_event(
                    item_id="movie-3",
                    status="skipped",
                    message="Cleanup item was not planned",
                ),
            )
        )

        failed = entry.events_for("preview_failed")

        self.assertEqual(len(failed), 1)
        self.assertEqual(
            failed[0].item_id,
            "movie-2",
        )

    def test_events_for_rejects_invalid_status(self) -> None:
        entry = make_entry()

        with self.assertRaisesRegex(
            CleanupHistoryError,
            "invalid cleanup execution event status",
        ):
            entry.events_for("unknown")

    def test_rejects_empty_events(self) -> None:
        with self.assertRaisesRegex(
            CleanupHistoryError,
            "events must contain at least one event",
        ):
            make_entry(events=())

    def test_rejects_non_tuple_events(self) -> None:
        with self.assertRaisesRegex(
            CleanupHistoryError,
            "events must be a tuple",
        ):
            CleanupHistoryEntry(
                execution_id=EXECUTION_ID,
                provider="jellyfin",
                mode=CleanupExecutionMode.DRY_RUN,
                events=[make_event()],
            )

    def test_rejects_invalid_event_members(self) -> None:
        with self.assertRaisesRegex(
            CleanupHistoryError,
            "CleanupExecutionEvent",
        ):
            CleanupHistoryEntry(
                execution_id=EXECUTION_ID,
                provider="jellyfin",
                mode=CleanupExecutionMode.DRY_RUN,
                events=(object(),),
            )

    def test_rejects_execution_identity_mismatch(
        self,
    ) -> None:
        event = make_event(
            execution_id=(
                "cln_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            )
        )

        with self.assertRaisesRegex(
            CleanupHistoryError,
            "event execution_id does not match",
        ):
            make_entry(events=(event,))

    def test_rejects_provider_mismatch(self) -> None:
        event = make_event(provider="emby")

        with self.assertRaisesRegex(
            CleanupHistoryError,
            "event provider does not match",
        ):
            make_entry(events=(event,))

    def test_rejects_mode_mismatch(self) -> None:
        event = make_event()

        with self.assertRaisesRegex(
            CleanupHistoryError,
            "event mode does not match",
        ):
            CleanupHistoryEntry(
                execution_id=EXECUTION_ID,
                provider="jellyfin",
                mode=CleanupExecutionMode.EXECUTE,
                events=(event,),
            )

    def test_rejects_duplicate_item_ids(self) -> None:
        with self.assertRaisesRegex(
            CleanupHistoryError,
            "duplicate item IDs",
        ):
            make_entry(
                events=(
                    make_event(
                        item_id="movie-1",
                        occurred_at=EARLY,
                    ),
                    make_event(
                        item_id="movie-1",
                        occurred_at=LATE,
                    ),
                )
            )

    def test_serializes_normalized_contract(self) -> None:
        eastern = timezone(timedelta(hours=-4))

        entry = make_entry(
            events=(
                make_event(
                    item_id="movie-2",
                    status="preview_failed",
                    message="Provider unavailable",
                    occurred_at=datetime(
                        2026,
                        7,
                        24,
                        8,
                        1,
                        tzinfo=eastern,
                    ),
                ),
                make_event(
                    item_id="movie-1",
                    occurred_at=datetime(
                        2026,
                        7,
                        24,
                        8,
                        0,
                        tzinfo=eastern,
                    ),
                ),
            )
        )

        self.assertEqual(
            entry.to_dict(),
            {
                "execution_id": EXECUTION_ID,
                "provider": "jellyfin",
                "mode": "dry_run",
                "started_at": "2026-07-24T12:00:00Z",
                "completed_at": "2026-07-24T12:01:00Z",
                "total": 2,
                "skipped": 0,
                "preview_succeeded": 1,
                "preview_failed": 1,
                "modified": 0,
                "successful": 1,
                "failed": 1,
                "has_failures": True,
                "events": [
                    make_event(
                        item_id="movie-1",
                        occurred_at=datetime(
                            2026,
                            7,
                            24,
                            8,
                            0,
                            tzinfo=eastern,
                        ),
                    ).to_dict(),
                    make_event(
                        item_id="movie-2",
                        status="preview_failed",
                        message="Provider unavailable",
                        occurred_at=datetime(
                            2026,
                            7,
                            24,
                            8,
                            1,
                            tzinfo=eastern,
                        ),
                    ).to_dict(),
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
