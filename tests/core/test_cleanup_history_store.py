"""Tests for cleanup JSONL history persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from atlas.cleanup.execution_events import (
    CleanupExecutionEvent,
    CleanupExecutionEventStatus,
)
from atlas.cleanup.history_models import (
    CleanupHistoryError,
)
from atlas.cleanup.history_store import (
    CleanupHistoryStore,
    JsonlCleanupHistoryStore,
)
from atlas.cleanup.models import CleanupAction


EXECUTION_ID_1 = "cln_0123456789abcdef0123456789abcdef"
EXECUTION_ID_2 = "cln_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

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
    13,
    0,
    tzinfo=timezone.utc,
)


def make_event(
    *,
    execution_id: str = EXECUTION_ID_1,
    provider: str = "jellyfin",
    item_id: str = "movie-1",
    status: CleanupExecutionEventStatus | str = (
        CleanupExecutionEventStatus.PREVIEW_SUCCEEDED
    ),
    message: str = "Preview verified",
    occurred_at: datetime = EARLY,
) -> CleanupExecutionEvent:
    """Create one deterministic persisted event."""

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
        status=status,
        message=message,
        occurred_at=occurred_at,
    )


def write_events(
    path: Path,
    *events: CleanupExecutionEvent,
) -> None:
    """Write deterministic compact JSONL events."""

    path.write_text(
        "".join(
            json.dumps(
                event.to_dict(),
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
            for event in events
        ),
        encoding="utf-8",
    )


class CleanupHistoryStoreTests(unittest.TestCase):
    """Tests for CleanupHistoryStore."""

    def test_store_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            CleanupHistoryStore()


class JsonlCleanupHistoryStoreTests(unittest.TestCase):
    """Tests for JsonlCleanupHistoryStore."""

    def test_missing_file_returns_empty_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"

            store = JsonlCleanupHistoryStore(path)

            self.assertEqual(
                store.list_entries(),
                (),
            )

    def test_reads_and_groups_execution_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"

            write_events(
                path,
                make_event(
                    execution_id=EXECUTION_ID_1,
                    item_id="movie-1",
                    occurred_at=EARLY,
                ),
                make_event(
                    execution_id=EXECUTION_ID_2,
                    item_id="movie-3",
                    occurred_at=LATE,
                ),
                make_event(
                    execution_id=EXECUTION_ID_1,
                    item_id="movie-2",
                    status="preview_failed",
                    message="Provider unavailable",
                    occurred_at=EARLY,
                ),
            )

            entries = JsonlCleanupHistoryStore(
                path
            ).list_entries()

            self.assertEqual(len(entries), 2)

            self.assertEqual(
                entries[0].execution_id,
                EXECUTION_ID_2,
            )
            self.assertEqual(entries[0].total, 1)

            self.assertEqual(
                entries[1].execution_id,
                EXECUTION_ID_1,
            )
            self.assertEqual(entries[1].total, 2)
            self.assertEqual(
                entries[1].preview_failed_count,
                1,
            )

    def test_orders_newest_execution_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"

            write_events(
                path,
                make_event(
                    execution_id=EXECUTION_ID_1,
                    item_id="movie-1",
                    occurred_at=EARLY,
                ),
                make_event(
                    execution_id=EXECUTION_ID_2,
                    item_id="movie-2",
                    occurred_at=LATE,
                ),
            )

            entries = JsonlCleanupHistoryStore(
                path
            ).list_entries()

            self.assertEqual(
                tuple(
                    entry.execution_id
                    for entry in entries
                ),
                (
                    EXECUTION_ID_2,
                    EXECUTION_ID_1,
                ),
            )

    def test_ignores_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            event = make_event()

            path.write_text(
                "\n"
                + json.dumps(event.to_dict())
                + "\n\n",
                encoding="utf-8",
            )

            entries = JsonlCleanupHistoryStore(
                path
            ).list_entries()

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].total, 1)

    def test_accepts_string_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"

            store = JsonlCleanupHistoryStore(
                str(path)
            )

            self.assertEqual(store.path, path)

    def test_rejects_empty_string_path(self) -> None:
        with self.assertRaisesRegex(
            CleanupHistoryError,
            "path must not be empty",
        ):
            JsonlCleanupHistoryStore(" ")

    def test_rejects_invalid_path_type(self) -> None:
        with self.assertRaisesRegex(
            CleanupHistoryError,
            "path must be a pathlib.Path or string",
        ):
            JsonlCleanupHistoryStore(object())

    def test_rejects_directory_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                CleanupHistoryError,
                "path must reference a file",
            ):
                JsonlCleanupHistoryStore(
                    Path(directory)
                )

    def test_reports_malformed_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"

            path.write_text(
                json.dumps(make_event().to_dict())
                + "\n"
                + "{bad json}\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                CleanupHistoryError,
                "line 2",
            ):
                JsonlCleanupHistoryStore(
                    path
                ).list_entries()

    def test_rejects_non_object_json_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"

            path.write_text(
                "[]\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                CleanupHistoryError,
                "JSON value must be an object",
            ):
                JsonlCleanupHistoryStore(
                    path
                ).list_entries()

    def test_rejects_missing_event_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            payload = make_event().to_dict()
            del payload["item_id"]

            path.write_text(
                json.dumps(payload) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                CleanupHistoryError,
                "missing required fields: item_id",
            ):
                JsonlCleanupHistoryStore(
                    path
                ).list_entries()

    def test_rejects_unexpected_event_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            payload = make_event().to_dict()
            payload["unknown"] = True

            path.write_text(
                json.dumps(payload) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                CleanupHistoryError,
                "unexpected fields: unknown",
            ):
                JsonlCleanupHistoryStore(
                    path
                ).list_entries()

    def test_rejects_invalid_event_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            payload = make_event().to_dict()
            payload["provider"] = " "

            path.write_text(
                json.dumps(payload) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                CleanupHistoryError,
                "provider must not be empty",
            ):
                JsonlCleanupHistoryStore(
                    path
                ).list_entries()

    def test_rejects_cross_event_contract_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"

            write_events(
                path,
                make_event(
                    execution_id=EXECUTION_ID_1,
                    provider="jellyfin",
                    item_id="movie-1",
                ),
                make_event(
                    execution_id=EXECUTION_ID_1,
                    provider="emby",
                    item_id="movie-2",
                ),
            )

            with self.assertRaisesRegex(
                CleanupHistoryError,
                "event provider does not match",
            ):
                JsonlCleanupHistoryStore(
                    path
                ).list_entries()

    @patch(
        "atlas.cleanup.history_store.Path.read_text",
        side_effect=OSError("disk unavailable"),
    )
    def test_wraps_filesystem_errors(
        self,
        read_text_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            path.touch()

            store = JsonlCleanupHistoryStore(path)

            with self.assertRaisesRegex(
                CleanupHistoryError,
                "failed to read cleanup history",
            ) as context:
                store.list_entries()

            self.assertIsInstance(
                context.exception.__cause__,
                OSError,
            )
            read_text_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
