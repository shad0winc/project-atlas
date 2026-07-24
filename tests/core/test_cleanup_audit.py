"""Tests for cleanup JSONL audit persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from atlas.cleanup import (
    CleanupAction,
    CleanupAuditError,
    CleanupAuditWriter,
    CleanupExecutionEvent,
    CleanupExecutionEventStatus,
    JsonlCleanupAuditWriter,
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
    item_id: str = "movie-1",
    status: CleanupExecutionEventStatus = (
        CleanupExecutionEventStatus.PREVIEW_SUCCEEDED
    ),
    message: str = "Preview verified",
) -> CleanupExecutionEvent:
    """Create one deterministic cleanup execution event."""

    return CleanupExecutionEvent(
        execution_id=EXECUTION_ID,
        provider="jellyfin",
        item_id=item_id,
        action=CleanupAction.DELETE,
        status=status,
        message=message,
        occurred_at=OCCURRED_AT,
    )


class CleanupAuditWriterTests(unittest.TestCase):
    """Tests for CleanupAuditWriter."""

    def test_writer_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            CleanupAuditWriter()


class JsonlCleanupAuditWriterTests(unittest.TestCase):
    """Tests for JsonlCleanupAuditWriter."""

    def test_writes_one_compact_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            writer = JsonlCleanupAuditWriter(
                path,
                durable=False,
            )

            event = make_event()

            writer.write(event)

            content = path.read_text(encoding="utf-8")

            self.assertEqual(content.count("\n"), 1)
            self.assertTrue(content.endswith("\n"))
            self.assertEqual(
                json.loads(content),
                event.to_dict(),
            )
            self.assertNotIn(": ", content)
            self.assertNotIn(", ", content)

    def test_appends_without_truncating_existing_events(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            writer = JsonlCleanupAuditWriter(
                path,
                durable=False,
            )

            first = make_event(item_id="movie-1")
            second = make_event(
                item_id="movie-2",
                status=(
                    CleanupExecutionEventStatus.PREVIEW_FAILED
                ),
                message="Provider unavailable",
            )

            writer.write(first)
            writer.write(second)

            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()

            self.assertEqual(len(lines), 2)
            self.assertEqual(
                json.loads(lines[0]),
                first.to_dict(),
            )
            self.assertEqual(
                json.loads(lines[1]),
                second.to_dict(),
            )

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = (
                Path(directory)
                / "nested"
                / "cleanup"
                / "audit.jsonl"
            )

            writer = JsonlCleanupAuditWriter(
                path,
                durable=False,
            )

            writer.write(make_event())

            self.assertTrue(path.is_file())

    def test_accepts_string_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"

            writer = JsonlCleanupAuditWriter(
                str(path),
                durable=False,
            )

            self.assertEqual(writer.path, path)

    def test_exposes_durability_setting(self) -> None:
        writer = JsonlCleanupAuditWriter(
            "audit.jsonl",
            durable=False,
        )

        self.assertFalse(writer.durable)

    def test_defaults_to_durable_writes(self) -> None:
        writer = JsonlCleanupAuditWriter(
            "audit.jsonl"
        )

        self.assertTrue(writer.durable)

    @patch("atlas.cleanup.audit.os.fsync")
    def test_durable_write_calls_fsync(
        self,
        fsync_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = JsonlCleanupAuditWriter(
                Path(directory) / "audit.jsonl",
                durable=True,
            )

            writer.write(make_event())

            fsync_mock.assert_called_once()

    @patch("atlas.cleanup.audit.os.fsync")
    def test_non_durable_write_skips_fsync(
        self,
        fsync_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            writer = JsonlCleanupAuditWriter(
                Path(directory) / "audit.jsonl",
                durable=False,
            )

            writer.write(make_event())

            fsync_mock.assert_not_called()

    def test_rejects_invalid_event_type(self) -> None:
        writer = JsonlCleanupAuditWriter(
            "audit.jsonl",
            durable=False,
        )

        with self.assertRaisesRegex(
            CleanupAuditError,
            "event must be a CleanupExecutionEvent",
        ):
            writer.write(object())

    def test_rejects_empty_string_path(self) -> None:
        with self.assertRaisesRegex(
            CleanupAuditError,
            "path must not be empty",
        ):
            JsonlCleanupAuditWriter(" ")

    def test_rejects_invalid_path_type(self) -> None:
        with self.assertRaisesRegex(
            CleanupAuditError,
            "path must be a pathlib.Path or string",
        ):
            JsonlCleanupAuditWriter(object())

    def test_rejects_directory_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                CleanupAuditError,
                "path must reference a file",
            ):
                JsonlCleanupAuditWriter(
                    Path(directory)
                )

    def test_rejects_invalid_durable_value(self) -> None:
        with self.assertRaisesRegex(
            CleanupAuditError,
            "durable must be a boolean",
        ):
            JsonlCleanupAuditWriter(
                "audit.jsonl",
                durable="yes",
            )

    @patch(
        "atlas.cleanup.audit.Path.open",
        side_effect=OSError("disk unavailable"),
    )
    def test_wraps_filesystem_errors(
        self,
        open_mock,
    ) -> None:
        writer = JsonlCleanupAuditWriter(
            "audit.jsonl",
            durable=False,
        )

        with self.assertRaisesRegex(
            CleanupAuditError,
            "failed to append cleanup audit event",
        ) as context:
            writer.write(make_event())

        self.assertIsInstance(
            context.exception.__cause__,
            OSError,
        )
        open_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
