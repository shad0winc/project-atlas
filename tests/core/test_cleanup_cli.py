"""Tests for the Atlas Cleanup CLI."""

from __future__ import annotations

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import Mock

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
)
from atlas.cleanup_cli import main
from atlas.policies.models import (
    PolicyAction,
    PolicyDecision,
    PolicyReason,
)
from atlas.retention.models import RetentionDecision


def _cleanup_decision(
    *,
    eligible: bool,
    provider: str = "jellyfin",
    item_id: str = "item-123",
) -> CleanupDecision:
    reasons = ()

    if not eligible:
        reasons = (
            PolicyReason(
                code="favorite",
                source="favorites",
                detail="Favorited by an Atlas user",
            ),
        )

    policy = PolicyDecision(
        provider=provider,
        item_id=item_id,
        action=(
            PolicyAction.IGNORE
            if eligible
            else PolicyAction.PROTECT
        ),
        reasons=reasons,
    )

    retention = RetentionDecision(
        provider=provider,
        item_id=item_id,
        eligible=eligible,
        policy=policy,
    )

    return CleanupDecision(
        provider=provider,
        item_id=item_id,
        action=(
            CleanupAction.DELETE
            if eligible
            else CleanupAction.KEEP
        ),
        retention=retention,
    )


class CleanupCliTests(unittest.TestCase):
    """Validate cleanup command-line behavior."""

    def test_evaluate_human_output(self) -> None:
        service = Mock()
        service.evaluate.return_value = _cleanup_decision(
            eligible=False,
        )
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                [
                    "evaluate",
                    "jellyfin",
                    "item-123",
                ],
                service=service,
            )

        rendered = output.getvalue()

        self.assertEqual(result, 0)
        self.assertIn(
            "Atlas Cleanup Decision",
            rendered,
        )
        self.assertIn(
            "Action: keep",
            rendered,
        )
        self.assertIn(
            "Eligible for cleanup: False",
            rendered,
        )
        self.assertIn(
            "Retained by Atlas: True",
            rendered,
        )
        self.assertIn(
            "[favorites] favorite",
            rendered,
        )

    def test_evaluate_json_output(self) -> None:
        service = Mock()
        service.evaluate.return_value = _cleanup_decision(
            eligible=True,
        )
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                [
                    "evaluate",
                    "jellyfin",
                    "item-123",
                    "--json",
                ],
                service=service,
            )

        payload = json.loads(output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(payload["provider"], "jellyfin")
        self.assertEqual(payload["item_id"], "item-123")
        self.assertEqual(payload["action"], "delete")
        self.assertTrue(payload["retention"]["eligible"])
        self.assertFalse(payload["retention"]["retained"])

    def test_evaluate_passes_provider_and_item_id(
        self,
    ) -> None:
        service = Mock()
        service.evaluate.return_value = _cleanup_decision(
            eligible=True,
            provider="emby",
            item_id="custom-item",
        )

        with redirect_stdout(StringIO()):
            result = main(
                [
                    "evaluate",
                    "emby",
                    "custom-item",
                ],
                service=service,
            )

        self.assertEqual(result, 0)
        service.evaluate.assert_called_once_with(
            "emby",
            "custom-item",
        )

    def test_evaluate_returns_nonzero_on_cleanup_error(
        self,
    ) -> None:
        service = Mock()
        service.evaluate.side_effect = CleanupError(
            "invalid cleanup request"
        )
        error_output = StringIO()

        with redirect_stderr(error_output):
            result = main(
                [
                    "evaluate",
                    "jellyfin",
                    "item-123",
                ],
                service=service,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup evaluation failed",
            error_output.getvalue(),
        )
        self.assertIn(
            "invalid cleanup request",
            error_output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
