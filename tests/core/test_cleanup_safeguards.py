"""Cross-boundary automatic cleanup safety tests for Project Atlas."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from atlas.cleanup.models import CleanupAction
from atlas.cleanup.scanner import CleanupScanner
from atlas.cleanup.service import CleanupService
from atlas.cleanup.workflow import CleanupWorkflowService
from atlas.favorites import FavoriteStore
from atlas.integrations.maintainerr import MaintainerrIntegration
from atlas.media import (
    ProviderCapabilities,
    ProviderCapability,
    ProviderMutationResult,
    ProviderOperation,
)
from atlas.policies import PolicyService
from atlas.policies.providers import PolicyProviders
from atlas.retention import RetentionService


USER_A = "usr_" + "a" * 32


class FailingPolicyService:
    """Policy boundary that deterministically fails closed in tests."""

    def evaluate(self, provider: str, item_id: str):
        del provider, item_id
        raise RuntimeError("policy state unavailable")


class CleanupSafetyTests(unittest.TestCase):
    """Prove protection and failure state cannot become media mutation."""

    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.favorites = FavoriteStore(Path(self.tempdir.name))
        self.policy_service = PolicyService(
            providers=PolicyProviders(favorites=self.favorites),
        )
        self.retention_service = RetentionService(
            policy_service=self.policy_service,
        )
        self.cleanup_service = CleanupService(
            retention_service=self.retention_service,
        )
        self.scanner = CleanupScanner(self.cleanup_service)

    @staticmethod
    def _provider(*item_ids: str) -> Mock:
        """Return a provider-shaped mock with observable preview calls."""

        provider = Mock()
        provider.name = "jellyfin"
        provider.get_capabilities.return_value = ProviderCapabilities(
            provider="jellyfin",
            capabilities=frozenset(
                {
                    ProviderCapability.LIST_MEDIA,
                    ProviderCapability.PREVIEW_DELETE,
                }
            ),
            supports_batch_listing=True,
            supports_batch_preview=False,
            max_batch_size=200,
        )
        provider.list_media_item_ids.return_value = tuple(item_ids)

        def preview_delete_item(item_id: str) -> ProviderMutationResult:
            return ProviderMutationResult(
                provider="jellyfin",
                operation=ProviderOperation.DELETE,
                item_id=item_id,
                success=True,
                message="Preview recorded",
                executed_at="2026-08-06T23:55:00Z",
            )

        provider.preview_delete_item.side_effect = preview_delete_item
        return provider

    def test_favorite_protection_skips_provider_preview(self) -> None:
        """A favorite must become KEEP before the provider boundary."""

        self.favorites.add(
            USER_A,
            "jellyfin",
            "movie-1",
            media_type="movie",
            title="Arrival",
        )
        provider = self._provider("movie-1")
        workflow = CleanupWorkflowService(scanner=self.scanner)

        summary = workflow.execute(provider)

        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.planned, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(summary.modified, 0)
        provider.preview_delete_item.assert_not_called()

        decision = self.cleanup_service.evaluate(
            "jellyfin",
            "movie-1",
        )
        self.assertIs(decision.action, CleanupAction.KEEP)
        self.assertTrue(decision.retention.policy.protected)
        self.assertEqual(
            decision.retention.policy.reasons[0].code,
            "favorite",
        )

    def test_eligible_media_reaches_preview_without_modification(self) -> None:
        """Eligible media may be previewed but never modified by v1 cleanup."""

        provider = self._provider("movie-1")
        workflow = CleanupWorkflowService(scanner=self.scanner)

        summary = workflow.execute(provider)

        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.planned, 1)
        self.assertEqual(summary.skipped, 0)
        self.assertEqual(summary.modified, 0)
        provider.preview_delete_item.assert_called_once_with("movie-1")

    def test_policy_failure_stops_before_provider_preview(self) -> None:
        """Unavailable policy state must fail before provider action."""

        retention = RetentionService(
            policy_service=FailingPolicyService(),  # type: ignore[arg-type]
        )
        scanner = CleanupScanner(
            CleanupService(retention_service=retention)
        )
        provider = self._provider("movie-1")
        workflow = CleanupWorkflowService(scanner=scanner)

        with self.assertRaisesRegex(
            RuntimeError,
            "policy state unavailable",
        ):
            workflow.execute(provider)

        provider.preview_delete_item.assert_not_called()

    def test_execute_mode_is_rejected_before_provider_preview(self) -> None:
        """The current workflow must reject destructive execution mode."""

        provider = self._provider("movie-1")
        workflow = CleanupWorkflowService(scanner=self.scanner)

        with self.assertRaisesRegex(
            ValueError,
            "only dry-run cleanup execution is supported",
        ):
            workflow.execute(provider, mode="execute")

        provider.preview_delete_item.assert_not_called()

    def test_maintainerr_denies_favorited_media(self) -> None:
        """Maintainerr assessment must consume the same protection chain."""

        self.favorites.add(
            USER_A,
            "jellyfin",
            "movie-1",
            media_type="movie",
            title="Arrival",
        )
        integration = MaintainerrIntegration(
            cleanup_service=self.cleanup_service,
        )

        assessment = integration.evaluate("jellyfin", "movie-1")

        self.assertTrue(assessment.denied)
        self.assertFalse(assessment.can_delete)
        self.assertIsNotNone(assessment.decision)
        assert assessment.decision is not None
        self.assertIs(
            assessment.decision.action,
            CleanupAction.KEEP,
        )

    def test_final_favorite_removal_requires_fresh_assessment(self) -> None:
        """A later decision may change only after protection is re-evaluated."""

        favorite = self.favorites.add(
            USER_A,
            "jellyfin",
            "movie-1",
            media_type="movie",
            title="Arrival",
        )
        integration = MaintainerrIntegration(
            cleanup_service=self.cleanup_service,
        )

        protected = integration.evaluate("jellyfin", "movie-1")
        self.assertTrue(protected.denied)

        self.favorites.remove(favorite["favorite_id"])

        refreshed = integration.evaluate("jellyfin", "movie-1")
        self.assertFalse(refreshed.denied)
        self.assertTrue(refreshed.can_delete)
        self.assertIsNotNone(refreshed.decision)
        assert refreshed.decision is not None
        self.assertIs(
            refreshed.decision.action,
            CleanupAction.DELETE,
        )


if __name__ == "__main__":
    unittest.main()
