"""Tests for the Atlas Maintainerr integration boundary."""

from __future__ import annotations

import unittest

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
)
from atlas.integrations.maintainerr import (
    MaintainerrAssessment,
    MaintainerrIntegration,
    MaintainerrIntegrationError,
)
from atlas.policies.models import (
    PolicyAction,
    PolicyDecision,
)
from atlas.retention.models import RetentionDecision


class RecordingCleanupService:
    """Small cleanup-service test double."""

    def __init__(
        self,
        result: object = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> object:
        self.calls.append(
            (
                provider,
                item_id,
            )
        )

        if self.error is not None:
            raise self.error

        return self.result


def build_cleanup_decision(
    action: CleanupAction,
    *,
    provider: str = "jellyfin",
    item_id: str = "item-1",
) -> CleanupDecision:
    """Build a normalized cleanup decision for testing."""

    policy_action = (
        PolicyAction.IGNORE
        if action is CleanupAction.DELETE
        else PolicyAction.PROTECT
    )

    policy = PolicyDecision(
        provider=provider,
        item_id=item_id,
        action=policy_action,
        reasons=(),
    )

    retention = RetentionDecision(
        provider=provider,
        item_id=item_id,
        eligible=(
            action is CleanupAction.DELETE
        ),
        policy=policy,
    )

    return CleanupDecision(
        provider=provider,
        item_id=item_id,
        action=action,
        retention=retention,
    )


class MaintainerrAssessmentTests(unittest.TestCase):
    """Validate the normalized Maintainerr assessment contract."""

    def test_delete_decision_allows_deletion(self) -> None:
        decision = build_cleanup_decision(
            CleanupAction.DELETE,
        )

        assessment = MaintainerrAssessment(
            provider="JELLYFIN",
            item_id="item-1",
            can_delete=True,
            decision=decision,
        )

        self.assertEqual(
            assessment.provider,
            "jellyfin",
        )
        self.assertTrue(
            assessment.can_delete,
        )
        self.assertFalse(
            assessment.denied,
        )
        self.assertIs(
            assessment.decision,
            decision,
        )
        self.assertIsNone(
            assessment.error,
        )

    def test_keep_decision_denies_deletion(self) -> None:
        decision = build_cleanup_decision(
            CleanupAction.KEEP,
        )

        assessment = MaintainerrAssessment(
            provider="jellyfin",
            item_id="item-1",
            can_delete=False,
            decision=decision,
        )

        self.assertFalse(
            assessment.can_delete,
        )
        self.assertTrue(
            assessment.denied,
        )

    def test_review_decision_denies_deletion(self) -> None:
        decision = build_cleanup_decision(
            CleanupAction.REVIEW,
        )

        assessment = MaintainerrAssessment(
            provider="jellyfin",
            item_id="item-1",
            can_delete=False,
            decision=decision,
        )

        self.assertTrue(
            assessment.denied,
        )

    def test_error_only_assessment_is_fail_closed(self) -> None:
        assessment = MaintainerrAssessment(
            provider="jellyfin",
            item_id="item-1",
            can_delete=False,
            error="policy service unavailable",
        )

        self.assertTrue(
            assessment.denied,
        )
        self.assertIsNone(
            assessment.decision,
        )

    def test_rejects_boolean_that_disagrees_with_decision(self) -> None:
        decision = build_cleanup_decision(
            CleanupAction.KEEP,
        )

        with self.assertRaises(
            MaintainerrIntegrationError,
        ):
            MaintainerrAssessment(
                provider="jellyfin",
                item_id="item-1",
                can_delete=True,
                decision=decision,
            )


class MaintainerrIntegrationTests(unittest.TestCase):
    """Validate Maintainerr authorization behavior."""

    def test_delete_decision_allows_maintainerr(self) -> None:
        decision = build_cleanup_decision(
            CleanupAction.DELETE,
        )

        cleanup_service = RecordingCleanupService(
            result=decision,
        )

        integration = MaintainerrIntegration(
            cleanup_service=cleanup_service,
        )

        assessment = integration.evaluate(
            " JELLYFIN ",
            " item-1 ",
        )

        self.assertTrue(
            assessment.can_delete,
        )
        self.assertIs(
            assessment.decision,
            decision,
        )
        self.assertEqual(
            cleanup_service.calls,
            [
                (
                    "jellyfin",
                    "item-1",
                ),
            ],
        )

    def test_keep_decision_denies_maintainerr(self) -> None:
        decision = build_cleanup_decision(
            CleanupAction.KEEP,
        )

        integration = MaintainerrIntegration(
            cleanup_service=RecordingCleanupService(
                result=decision,
            ),
        )

        assessment = integration.evaluate(
            "jellyfin",
            "item-1",
        )

        self.assertFalse(
            assessment.can_delete,
        )
        self.assertTrue(
            assessment.denied,
        )
        self.assertIs(
            assessment.decision,
            decision,
        )

    def test_review_decision_denies_maintainerr(self) -> None:
        decision = build_cleanup_decision(
            CleanupAction.REVIEW,
        )

        integration = MaintainerrIntegration(
            cleanup_service=RecordingCleanupService(
                result=decision,
            ),
        )

        assessment = integration.evaluate(
            "jellyfin",
            "item-1",
        )

        self.assertFalse(
            assessment.can_delete,
        )
        self.assertTrue(
            assessment.denied,
        )

    def test_cleanup_failure_denies_deletion(self) -> None:
        integration = MaintainerrIntegration(
            cleanup_service=RecordingCleanupService(
                error=RuntimeError(
                    "retention unavailable"
                ),
            ),
        )

        assessment = integration.evaluate(
            "jellyfin",
            "item-1",
        )

        self.assertFalse(
            assessment.can_delete,
        )
        self.assertTrue(
            assessment.denied,
        )
        self.assertIsNone(
            assessment.decision,
        )
        self.assertEqual(
            assessment.error,
            "retention unavailable",
        )

    def test_invalid_cleanup_result_denies_deletion(self) -> None:
        integration = MaintainerrIntegration(
            cleanup_service=RecordingCleanupService(
                result={"action": "delete"},
            ),
        )

        assessment = integration.evaluate(
            "jellyfin",
            "item-1",
        )

        self.assertFalse(
            assessment.can_delete,
        )
        self.assertIn(
            "CleanupDecision",
            assessment.error or "",
        )

    def test_mismatched_decision_identity_denies_deletion(self) -> None:
        decision = build_cleanup_decision(
            CleanupAction.DELETE,
            item_id="different-item",
        )

        integration = MaintainerrIntegration(
            cleanup_service=RecordingCleanupService(
                result=decision,
            ),
        )

        assessment = integration.evaluate(
            "jellyfin",
            "item-1",
        )

        self.assertFalse(
            assessment.can_delete,
        )
        self.assertIn(
            "identity",
            assessment.error or "",
        )

    def test_invalid_candidate_identity_is_rejected(self) -> None:
        integration = MaintainerrIntegration(
            cleanup_service=RecordingCleanupService(),
        )

        with self.assertRaises(
            MaintainerrIntegrationError,
        ):
            integration.evaluate(
                "",
                "item-1",
            )


if __name__ == "__main__":
    unittest.main()
