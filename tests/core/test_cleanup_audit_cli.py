"""Tests for cleanup audit CLI integration."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from atlas.cleanup.executor import (
    CleanupExecutionSummary,
    CleanupRunStatus,
)
from atlas.cleanup.execution_models import (
    CleanupExecutionMode,
)
from atlas.cleanup_cli import main



EXECUTION_ID = "cln_0123456789abcdef0123456789abcdef"

NOW = datetime(
    2026,
    7,
    24,
    0,
    0,
    tzinfo=timezone.utc,
)


def make_summary() -> CleanupExecutionSummary:
    """Create a deterministic successful workflow summary."""

    return CleanupExecutionSummary(
        execution_id=EXECUTION_ID,
        provider="jellyfin",
        mode=CleanupExecutionMode.DRY_RUN,
        status=CleanupRunStatus.SUCCESS,
        started_at="2026-07-24T00:00:00Z",
        completed_at="2026-07-24T00:00:01Z",
        total=0,
        planned=0,
        skipped=0,
        modified=0,
    )


class CleanupAuditCliTests(unittest.TestCase):
    """Validate cleanup audit dependency wiring."""

    @patch("atlas.cleanup_cli.CleanupWorkflowService")
    @patch("atlas.cleanup_cli.DefaultCleanupExecutor")
    @patch("atlas.cleanup_cli.JsonlCleanupAuditWriter")
    def test_run_uses_state_directory_audit_path(
        self,
        writer_class,
        executor_class,
        workflow_class,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = Mock()
            provider.name = "jellyfin"

            writer = writer_class.return_value
            executor = executor_class.return_value
            workflow = workflow_class.return_value
            workflow.execute.return_value = make_summary()

            stdout = StringIO()
            stderr = StringIO()

            with patch.dict(
                "os.environ",
                {
                    "ATLAS_STATE_DIR": directory,
                    "ATLAS_CLEANUP_AUDIT_PATH": "",
                },
                clear=False,
            ):
                with redirect_stdout(stdout):
                    with redirect_stderr(stderr):
                        result = main(
                            [
                                "run",
                                "jellyfin",
                                "--json",
                            ],
                            jellyfin_provider=provider,
                        )

            self.assertEqual(result, 0)
            self.assertEqual(stderr.getvalue(), "")

            writer_class.assert_called_once_with(
                (
                    Path(directory)
                    / "cleanup"
                    / "audit.jsonl"
                ),
                durable=True,
            )

            executor_class.assert_called_once_with(
                provider=provider,
                audit_writer=writer,
            )

            workflow_class.assert_called_once()
            self.assertIs(
                workflow_class.call_args.kwargs[
                    "executor"
                ],
                executor,
            )

            workflow.execute.assert_called_once_with(
                provider,
                page_size=200,
                mode="dry_run",
            )

    @patch("atlas.cleanup_cli.CleanupWorkflowService")
    @patch("atlas.cleanup_cli.DefaultCleanupExecutor")
    @patch("atlas.cleanup_cli.JsonlCleanupAuditWriter")
    def test_run_accepts_explicit_audit_path(
        self,
        writer_class,
        executor_class,
        workflow_class,
    ) -> None:
        provider = Mock()
        provider.name = "jellyfin"

        workflow = workflow_class.return_value
        workflow.execute.return_value = make_summary()

        stdout = StringIO()
        stderr = StringIO()

        with redirect_stdout(stdout):
            with redirect_stderr(stderr):
                result = main(
                    [
                        "run",
                        "jellyfin",
                        "--audit-path",
                        "/tmp/atlas-cleanup.jsonl",
                    ],
                    jellyfin_provider=provider,
                )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")

        writer_class.assert_called_once_with(
            "/tmp/atlas-cleanup.jsonl",
            durable=True,
        )

    @patch("atlas.cleanup_cli.JsonlCleanupAuditWriter")
    def test_injected_workflow_skips_audit_construction(
        self,
        writer_class,
    ) -> None:
        provider = Mock()
        provider.name = "jellyfin"

        workflow = Mock()
        workflow.execute.return_value = make_summary()

        stdout = StringIO()
        stderr = StringIO()

        with redirect_stdout(stdout):
            with redirect_stderr(stderr):
                result = main(
                    [
                        "run",
                        "jellyfin",
                    ],
                    workflow_service=workflow,
                    jellyfin_provider=provider,
                )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        writer_class.assert_not_called()

        workflow.execute.assert_called_once_with(
            provider,
            page_size=200,
            mode="dry_run",
        )


if __name__ == "__main__":
    unittest.main()
