"""Tests for the Atlas retention command-line interface."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from atlas import retention_cli
from atlas.policies.models import (
    PolicyAction,
    PolicyDecision,
    PolicyReason,
)
from atlas.retention.models import RetentionDecision


def _decision(*, retained: bool) -> RetentionDecision:
    reasons = ()

    if retained:
        reasons = (
            PolicyReason(
                code="favorite",
                source="favorites",
                detail="Favorited by an Atlas user",
            ),
        )

    policy = PolicyDecision(
        provider="jellyfin",
        item_id="item-123",
        action=(
            PolicyAction.PROTECT
            if retained
            else PolicyAction.IGNORE
        ),
        reasons=reasons,
    )

    return RetentionDecision(
        provider="jellyfin",
        item_id="item-123",
        eligible=not retained,
        policy=policy,
    )


class RetentionCliTests(unittest.TestCase):
    """Validate Retention CLI behavior."""

    @patch.object(retention_cli.RetentionService, "evaluate")
    def test_evaluate_human_output(self, mock_evaluate) -> None:
        mock_evaluate.return_value = _decision(retained=False)

        stdout = io.StringIO()

        with redirect_stdout(stdout):
            result = retention_cli.main(
                ["evaluate", "jellyfin", "item-123"]
            )

        output = stdout.getvalue()

        self.assertEqual(result, 0)
        self.assertIn("Atlas Retention Decision", output)
        self.assertIn("Provider: jellyfin", output)
        self.assertIn("Item ID: item-123", output)
        self.assertIn("Eligible for cleanup: Yes", output)
        self.assertIn("Retained by Atlas: No", output)
        self.assertIn("Policy action: ignore", output)
        self.assertIn("Reasons: None", output)

    @patch.object(retention_cli.RetentionService, "evaluate")
    def test_evaluate_json_output(self, mock_evaluate) -> None:
        mock_evaluate.return_value = _decision(retained=True)

        stdout = io.StringIO()

        with redirect_stdout(stdout):
            result = retention_cli.main(
                [
                    "evaluate",
                    "jellyfin",
                    "item-123",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(payload["provider"], "jellyfin")
        self.assertEqual(payload["item_id"], "item-123")
        self.assertFalse(payload["eligible"])
        self.assertTrue(payload["retained"])
        self.assertEqual(
            payload["policy"]["action"],
            "protect",
        )
        self.assertTrue(payload["policy"]["protected"])
        self.assertEqual(
            payload["policy"]["reasons"][0]["code"],
            "favorite",
        )
        self.assertEqual(
            payload["policy"]["reasons"][0]["source"],
            "favorites",
        )

    @patch.object(retention_cli.RetentionService, "evaluate")
    def test_evaluate_passes_provider_and_item_id(
        self,
        mock_evaluate,
    ) -> None:
        mock_evaluate.return_value = _decision(retained=False)

        stdout = io.StringIO()

        with redirect_stdout(stdout):
            result = retention_cli.main(
                ["evaluate", "emby", "custom-item"]
            )

        self.assertEqual(result, 0)
        mock_evaluate.assert_called_once_with(
            "emby",
            "custom-item",
        )

    @patch.object(retention_cli.RetentionService, "evaluate")
    def test_evaluate_returns_nonzero_on_retention_error(
        self,
        mock_evaluate,
    ) -> None:
        mock_evaluate.side_effect = retention_cli.RetentionError(
            "test failure"
        )

        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = retention_cli.main(
                ["evaluate", "jellyfin", "item-123"]
            )

        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "unable to evaluate retention: test failure",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
