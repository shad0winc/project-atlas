"""Tests for cleanup history CLI rendering."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from atlas.cleanup.execution_events import (
    CleanupExecutionEvent,
)
from atlas.cleanup.execution_models import (
    CleanupExecutionMode,
)
from atlas.cleanup.history_models import CleanupHistoryEntry
from atlas.cleanup_cli import render_history_human


EXECUTION_ID = "cln_0123456789abcdef0123456789abcdef"


def make_event(
    *,
    item_id: str,
    status: str,
    modified: bool = False,
    occurred_at: datetime,
) -> CleanupExecutionEvent:
    """Create one deterministic cleanup execution event."""

    return CleanupExecutionEvent(
        execution_id=EXECUTION_ID,
        provider="jellyfin",
        item_id=item_id,
        action="delete",
        mode="dry_run",
        status=status,
        message=f"{item_id}: {status}",
        modified=modified,
        occurred_at=occurred_at,
    )


def make_entry() -> CleanupHistoryEntry:
    """Create one deterministic cleanup history entry."""

    return CleanupHistoryEntry(
        execution_id=EXECUTION_ID,
        provider="jellyfin",
        mode=CleanupExecutionMode.DRY_RUN,
        events=(
            make_event(
                item_id="movie-1",
                status="preview_succeeded",
                occurred_at=datetime(
                    2026,
                    7,
                    24,
                    1,
                    0,
                    0,
                    tzinfo=timezone.utc,
                ),
            ),
            make_event(
                item_id="movie-2",
                status="preview_failed",
                occurred_at=datetime(
                    2026,
                    7,
                    24,
                    1,
                    0,
                    1,
                    tzinfo=timezone.utc,
                ),
            ),
            make_event(
                item_id="movie-3",
                status="skipped",
                occurred_at=datetime(
                    2026,
                    7,
                    24,
                    1,
                    0,
                    2,
                    tzinfo=timezone.utc,
                ),
            ),
        ),
    )


class CleanupHistoryCliRenderingTests(unittest.TestCase):
    """Validate cleanup history human-readable rendering."""

    def test_renders_empty_history(self) -> None:
        output = render_history_human(())

        self.assertEqual(
            output,
            "\n".join(
                [
                    "Atlas Cleanup History",
                    "---------------------",
                    "No cleanup execution history found.",
                ]
            ),
        )

    def test_renders_history_entry(self) -> None:
        output = render_history_human(
            (make_entry(),)
        )

        self.assertIn(
            "Atlas Cleanup History",
            output,
        )
        self.assertIn(
            f"Execution ID: {EXECUTION_ID}",
            output,
        )
        self.assertIn(
            "Provider: jellyfin",
            output,
        )
        self.assertIn(
            "Mode: dry_run",
            output,
        )
        self.assertIn(
            "Started at: 2026-07-24T01:00:00Z",
            output,
        )
        self.assertIn(
            "Completed at: 2026-07-24T01:00:02Z",
            output,
        )
        self.assertIn(
            "Total: 3",
            output,
        )
        self.assertIn(
            "Successful: 2",
            output,
        )
        self.assertIn(
            "Failed: 1",
            output,
        )
        self.assertIn(
            "Skipped: 1",
            output,
        )
        self.assertIn(
            "Preview succeeded: 1",
            output,
        )
        self.assertIn(
            "Preview failed: 1",
            output,
        )
        self.assertIn(
            "Modified: 0",
            output,
        )
        self.assertIn(
            "Has failures: True",
            output,
        )

    def test_renders_multiple_entries(self) -> None:
        first = make_entry()

        second = CleanupHistoryEntry(
            execution_id=(
                "cln_fedcba9876543210"
                "fedcba9876543210"
            ),
            provider="jellyfin",
            mode=CleanupExecutionMode.DRY_RUN,
            events=(
                CleanupExecutionEvent(
                    execution_id=(
                        "cln_fedcba9876543210"
                        "fedcba9876543210"
                    ),
                    provider="jellyfin",
                    item_id="movie-4",
                    action="keep",
                    mode="dry_run",
                    status="skipped",
                    message="movie-4 skipped",
                    modified=False,
                    occurred_at=datetime(
                        2026,
                        7,
                        24,
                        2,
                        0,
                        0,
                        tzinfo=timezone.utc,
                    ),
                ),
            ),
        )

        output = render_history_human(
            (
                first,
                second,
            )
        )

        self.assertEqual(
            output.count("Execution ID:"),
            2,
        )
        self.assertIn(
            first.execution_id,
            output,
        )
        self.assertIn(
            second.execution_id,
            output,
        )


if __name__ == "__main__":
    unittest.main()
