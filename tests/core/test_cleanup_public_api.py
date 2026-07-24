"""Tests for the public Atlas cleanup package API."""

from __future__ import annotations

import unittest

import atlas.cleanup as cleanup
from atlas.cleanup.default_executor import DefaultCleanupExecutor
from atlas.cleanup.execution_models import (
    CleanupExecutionItem,
    CleanupExecutionMode,
    CleanupExecutionReport,
    CleanupExecutionStatus,
)
from atlas.cleanup.execution_service import CleanupExecutionService
from atlas.cleanup.executor import (
    CleanupExecutionError,
    CleanupExecutionSummary,
    CleanupExecutor,
    CleanupRunStatus,
)
from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
)
from atlas.cleanup.scan_models import CleanupScanReport
from atlas.cleanup.scanner import CleanupScanner
from atlas.cleanup.service import CleanupService
from atlas.cleanup.workflow import CleanupWorkflowService


class CleanupPublicApiTests(unittest.TestCase):
    """Verify the supported atlas.cleanup import surface."""

    def test_public_cleanup_exports_are_available(
        self,
    ) -> None:
        expected = {
            "CleanupAction": CleanupAction,
            "CleanupDecision": CleanupDecision,
            "CleanupError": CleanupError,
            "CleanupExecutionError": CleanupExecutionError,
            "CleanupExecutionItem": CleanupExecutionItem,
            "CleanupExecutionMode": CleanupExecutionMode,
            "CleanupExecutionReport": CleanupExecutionReport,
            "CleanupExecutionService": CleanupExecutionService,
            "CleanupExecutionStatus": CleanupExecutionStatus,
            "CleanupExecutionSummary": CleanupExecutionSummary,
            "CleanupExecutor": CleanupExecutor,
            "CleanupRunStatus": CleanupRunStatus,
            "CleanupScanReport": CleanupScanReport,
            "CleanupScanner": CleanupScanner,
            "CleanupService": CleanupService,
            "CleanupWorkflowService": CleanupWorkflowService,
            "DefaultCleanupExecutor": DefaultCleanupExecutor,
        }

        for name, expected_value in expected.items():
            with self.subTest(name=name):
                self.assertIs(
                    getattr(cleanup, name),
                    expected_value,
                )

    def test_all_matches_supported_public_api(
        self,
    ) -> None:
        self.assertEqual(
            set(cleanup.__all__),
            {
                "CleanupAction",
                "CleanupAuditError",
                "CleanupAuditWriter",
                "CleanupDecision",
                "CleanupError",
                "CleanupExecutionError",
                "CleanupExecutionEvent",
                "CleanupExecutionEventStatus",
                "CleanupExecutionItem",
                "CleanupExecutionMode",
                "CleanupExecutionReport",
                "CleanupExecutionService",
                "CleanupExecutionStatus",
                "CleanupExecutionSummary",
                "CleanupExecutor",
                "CleanupRunStatus",
                "CleanupScanReport",
                "CleanupScanner",
                "CleanupService",
                "CleanupWorkflowService",
                "DefaultCleanupExecutor",
                "JsonlCleanupAuditWriter",
                "DEFAULT_ATLAS_STATE_DIR",
                "DEFAULT_CLEANUP_AUDIT_RELATIVE_PATH",
                "default_cleanup_audit_path",
            },
        )


if __name__ == "__main__":
    unittest.main()
