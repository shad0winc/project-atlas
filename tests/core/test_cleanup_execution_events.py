"""Tests for item-level cleanup execution events."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from atlas.cleanup import (
    CleanupAction,
    CleanupError,
    CleanupExecutionEvent,
    CleanupExecutionEventStatus,
    CleanupExecutionMode,
)


EXECUTION_ID = "cln_0123456789abcdef0123456789abcdef"

OCCURRED_AT = datetime(
    2026,
    7,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_event(
    *,
    execution_id: str = EXECUTION_ID,
    provider: str = "jellyfin",
    item_id: str = "movie-1",
    action: CleanupAction | str = CleanupAction.DELETE,
    status: CleanupExecutionEventStatus | str = (
        CleanupExecutionEventStatus.PREVIEW_SUCCEEDED
    ),
    message: str = "Preview verified",
    mode: CleanupExecutionMode | str = (
        CleanupExecutionMode.DRY_RUN
    ),
    modified: bool = False,
    occurred_at: datetime = OCCURRED_AT,
) -> CleanupExecutionEvent:
    """Create one deterministic execution event."""

    return CleanupExecutionEvent(
        execution_id=execution_id,
        provider=provider,
        item_id=item_id,
        action=action,
        status=status,
        message=message,
        mode=mode,
        modified=modified,
        occurred_at=occurred_at,
    )


class CleanupExecutionEventTests(unittest.TestCase):
    """Tests for CleanupExecutionEvent."""

    def test_preview_success_exposes_normalized_contract(
        self,
    ) -> None:
        event = make_event(
            provider=" JELLYFIN ",
            item_id=" movie-1 ",
            action="delete",
            status="preview_succeeded",
            message=" Preview verified ",
        )

        self.assertEqual(event.provider, "jellyfin")
        self.assertEqual(event.item_id, "movie-1")
        self.assertIs(event.action, CleanupAction.DELETE)
        self.assertIs(
            event.mode,
            CleanupExecutionMode.DRY_RUN,
        )
        self.assertIs(
            event.status,
            CleanupExecutionEventStatus.PREVIEW_SUCCEEDED,
        )
        self.assertEqual(event.message, "Preview verified")
        self.assertFalse(event.modified)
        self.assertTrue(event.successful)
        self.assertFalse(event.failed)

    def test_preview_failure_is_failed(self) -> None:
        event = make_event(
            status=(
                CleanupExecutionEventStatus.PREVIEW_FAILED
            ),
            message="Provider unavailable",
        )

        self.assertFalse(event.successful)
        self.assertTrue(event.failed)

    def test_skipped_event_is_successful(self) -> None:
        event = make_event(
            action=CleanupAction.KEEP,
            status=CleanupExecutionEventStatus.SKIPPED,
            message="Cleanup action is keep",
        )

        self.assertTrue(event.successful)
        self.assertFalse(event.failed)

    def test_delete_action_may_be_skipped(self) -> None:
        event = make_event(
            action=CleanupAction.DELETE,
            status=CleanupExecutionEventStatus.SKIPPED,
            message="Approval was not granted",
        )

        self.assertIs(event.action, CleanupAction.DELETE)
        self.assertIs(
            event.status,
            CleanupExecutionEventStatus.SKIPPED,
        )

    def test_preview_requires_delete_action(self) -> None:
        for action in (
            CleanupAction.KEEP,
            CleanupAction.REVIEW,
        ):
            with self.subTest(action=action):
                with self.assertRaisesRegex(
                    CleanupError,
                    "preview execution events require delete",
                ):
                    make_event(action=action)

    def test_dry_run_cannot_claim_media_was_modified(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "cannot modify media",
        ):
            make_event(modified=True)

    def test_rejects_invalid_identity_values(self) -> None:
        for field_name, overrides in (
            ("provider", {"provider": " "}),
            ("item_id", {"item_id": ""}),
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(
                    CleanupError,
                    f"{field_name} must not be empty",
                ):
                    make_event(**overrides)

    def test_rejects_empty_message(self) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "message must not be empty",
        ):
            make_event(message=" ")

    def test_rejects_invalid_status(self) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "invalid cleanup execution event status",
        ):
            make_event(status="unknown")

    def test_rejects_naive_timestamp(self) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "occurred_at must be timezone-aware",
        ):
            make_event(
                occurred_at=datetime(
                    2026,
                    7,
                    20,
                    12,
                    0,
                )
            )

    def test_normalizes_timestamp_to_utc(self) -> None:
        eastern = timezone(timedelta(hours=-4))

        event = make_event(
            occurred_at=datetime(
                2026,
                7,
                20,
                8,
                0,
                tzinfo=eastern,
            )
        )

        self.assertEqual(event.occurred_at, OCCURRED_AT)

    def test_serializes_normalized_contract(self) -> None:
        event = make_event()

        self.assertEqual(
            event.to_dict(),
            {
                "execution_id": EXECUTION_ID,
                "provider": "jellyfin",
                "item_id": "movie-1",
                "action": "delete",
                "mode": "dry_run",
                "status": "preview_succeeded",
                "message": "Preview verified",
                "modified": False,
                "occurred_at": "2026-07-20T12:00:00Z",
            },
        )


if __name__ == "__main__":
    unittest.main()
