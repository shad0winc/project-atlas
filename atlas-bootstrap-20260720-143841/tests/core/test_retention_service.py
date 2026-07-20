from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from atlas.favorites import FavoriteStore
from atlas.policies import (
    PolicyAction,
    PolicyDecision,
    PolicyService,
)
from atlas.policies.providers import PolicyProviders
from atlas.retention import (
    RetentionDecision,
    RetentionService,
)


USER_A = "usr_" + "a" * 32


class ServiceFixture:
    """Provides isolated retention-service dependencies."""

    def __init__(self) -> None:
        self.tempdir = TemporaryDirectory()

        self.favorites = FavoriteStore(
            Path(self.tempdir.name),
        )

        self.providers = PolicyProviders(
            favorites=self.favorites,
        )

        self.policy_service = PolicyService(
            providers=self.providers,
        )

        self.service = RetentionService(
            policy_service=self.policy_service,
        )

    def cleanup(self) -> None:
        self.tempdir.cleanup()


class StubPolicyService:
    """Returns a predetermined policy decision."""

    def __init__(
        self,
        decision: PolicyDecision,
    ) -> None:
        self.decision = decision
        self.calls: list[tuple[str, str]] = []

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> PolicyDecision:
        self.calls.append(
            (
                provider,
                item_id,
            ),
        )

        return self.decision


class RetentionServiceTests(unittest.TestCase):

    def test_unprotected_media_is_eligible(
        self,
    ) -> None:
        fixture = ServiceFixture()
        self.addCleanup(fixture.cleanup)

        decision = fixture.service.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertIsInstance(
            decision,
            RetentionDecision,
        )
        self.assertTrue(decision.eligible)
        self.assertFalse(decision.retained)
        self.assertEqual(
            PolicyAction.IGNORE,
            decision.policy.action,
        )

    def test_favorited_media_is_not_eligible(
        self,
    ) -> None:
        fixture = ServiceFixture()
        self.addCleanup(fixture.cleanup)

        fixture.favorites.add(
            USER_A,
            "jellyfin",
            "abc123",
            media_type="movie",
            title="Arrival",
        )

        decision = fixture.service.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertFalse(decision.eligible)
        self.assertTrue(decision.retained)
        self.assertTrue(decision.policy.protected)
        self.assertEqual(
            "favorite",
            decision.policy.reasons[0].code,
        )

    def test_service_can_be_reused_after_policy_state_changes(
        self,
    ) -> None:
        fixture = ServiceFixture()
        self.addCleanup(fixture.cleanup)

        first_decision = fixture.service.evaluate(
            "jellyfin",
            "abc123",
        )

        fixture.favorites.add(
            USER_A,
            "jellyfin",
            "abc123",
            media_type="movie",
        )

        second_decision = fixture.service.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertTrue(first_decision.eligible)
        self.assertFalse(second_decision.eligible)

    def test_release_policy_is_eligible(
        self,
    ) -> None:
        policy = PolicyDecision(
            provider="jellyfin",
            item_id="abc123",
            action=PolicyAction.RELEASE,
        )

        policy_service = StubPolicyService(
            policy,
        )

        service = RetentionService(
            policy_service=policy_service,  # type: ignore[arg-type]
        )

        decision = service.evaluate(
            "JELLYFIN",
            "abc123",
        )

        self.assertTrue(decision.eligible)
        self.assertFalse(decision.retained)
        self.assertEqual(
            PolicyAction.RELEASE,
            decision.policy.action,
        )
        self.assertEqual(
            [
                (
                    "JELLYFIN",
                    "abc123",
                ),
            ],
            policy_service.calls,
        )

    def test_service_uses_normalized_policy_identity(
        self,
    ) -> None:
        policy = PolicyDecision(
            provider="jellyfin",
            item_id="abc123",
            action=PolicyAction.IGNORE,
        )

        policy_service = StubPolicyService(
            policy,
        )

        service = RetentionService(
            policy_service=policy_service,  # type: ignore[arg-type]
        )

        decision = service.evaluate(
            " JELLYFIN ",
            " abc123 ",
        )

        self.assertEqual(
            "jellyfin",
            decision.provider,
        )
        self.assertEqual(
            "abc123",
            decision.item_id,
        )


if __name__ == "__main__":
    unittest.main()
