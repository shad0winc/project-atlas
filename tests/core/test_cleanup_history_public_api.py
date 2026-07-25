"""Tests for the public cleanup-history API."""

from __future__ import annotations

import unittest

import atlas.cleanup as cleanup
from atlas.cleanup.history_models import (
    CleanupHistoryEntry,
    CleanupHistoryError,
)
from atlas.cleanup.history_service import (
    CleanupHistoryService,
)
from atlas.cleanup.history_store import (
    CleanupHistoryStore,
    JsonlCleanupHistoryStore,
)


class CleanupHistoryPublicApiTests(unittest.TestCase):
    """Tests for cleanup-history package exports."""

    def test_exports_history_models(self) -> None:
        self.assertIs(
            cleanup.CleanupHistoryEntry,
            CleanupHistoryEntry,
        )
        self.assertIs(
            cleanup.CleanupHistoryError,
            CleanupHistoryError,
        )

    def test_exports_history_service(self) -> None:
        self.assertIs(
            cleanup.CleanupHistoryService,
            CleanupHistoryService,
        )

    def test_exports_history_stores(self) -> None:
        self.assertIs(
            cleanup.CleanupHistoryStore,
            CleanupHistoryStore,
        )
        self.assertIs(
            cleanup.JsonlCleanupHistoryStore,
            JsonlCleanupHistoryStore,
        )

    def test_declares_history_exports(self) -> None:
        expected = {
            "CleanupHistoryEntry",
            "CleanupHistoryError",
            "CleanupHistoryService",
            "CleanupHistoryStore",
            "JsonlCleanupHistoryStore",
        }

        self.assertTrue(
            expected.issubset(set(cleanup.__all__))
        )

    def test_history_exports_are_unique(self) -> None:
        history_exports = [
            name
            for name in cleanup.__all__
            if name
            in {
                "CleanupHistoryEntry",
                "CleanupHistoryError",
                "CleanupHistoryService",
                "CleanupHistoryStore",
                "JsonlCleanupHistoryStore",
            }
        ]

        self.assertEqual(
            len(history_exports),
            len(set(history_exports)),
        )


if __name__ == "__main__":
    unittest.main()
