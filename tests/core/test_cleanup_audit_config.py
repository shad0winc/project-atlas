"""Tests for cleanup audit configuration."""

from __future__ import annotations

import unittest
from pathlib import Path

from atlas.cleanup.audit_config import (
    DEFAULT_ATLAS_STATE_DIR,
    default_cleanup_audit_path,
)


class CleanupAuditConfigTests(unittest.TestCase):
    """Validate cleanup audit path resolution."""

    def test_explicit_audit_path_takes_precedence(
        self,
    ) -> None:
        result = default_cleanup_audit_path(
            {
                "ATLAS_CLEANUP_AUDIT_PATH": (
                    "/tmp/atlas/custom-cleanup.jsonl"
                ),
                "ATLAS_STATE_DIR": "/tmp/atlas/state",
            }
        )

        self.assertEqual(
            result,
            Path(
                "/tmp/atlas/custom-cleanup.jsonl"
            ),
        )

    def test_state_directory_builds_default_path(
        self,
    ) -> None:
        result = default_cleanup_audit_path(
            {
                "ATLAS_STATE_DIR": "/tmp/atlas-state",
            }
        )

        self.assertEqual(
            result,
            Path(
                "/tmp/atlas-state/cleanup/audit.jsonl"
            ),
        )

    def test_empty_explicit_path_uses_state_directory(
        self,
    ) -> None:
        result = default_cleanup_audit_path(
            {
                "ATLAS_CLEANUP_AUDIT_PATH": "   ",
                "ATLAS_STATE_DIR": "/tmp/state",
            }
        )

        self.assertEqual(
            result,
            Path(
                "/tmp/state/cleanup/audit.jsonl"
            ),
        )

    def test_default_path_uses_atlas_storage(
        self,
    ) -> None:
        result = default_cleanup_audit_path({})

        self.assertEqual(
            result,
            (
                DEFAULT_ATLAS_STATE_DIR
                / "cleanup"
                / "audit.jsonl"
            ),
        )

    def test_path_values_are_trimmed(
        self,
    ) -> None:
        result = default_cleanup_audit_path(
            {
                "ATLAS_CLEANUP_AUDIT_PATH": (
                    "  /tmp/audit.jsonl  "
                ),
            }
        )

        self.assertEqual(
            result,
            Path("/tmp/audit.jsonl"),
        )


if __name__ == "__main__":
    unittest.main()
