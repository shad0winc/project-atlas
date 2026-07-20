from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from atlas.favorites import FavoriteStore
from atlas.policies import (
    PolicyDecision,
    PolicyService,
)
from atlas.policies.favorites import FavoriteRule
from atlas.policies.providers import PolicyProviders


USER_A = "usr_" + "a" * 32


class ServiceFixture:
    """Provides isolated policy-service dependencies for each test."""

    def __init__(self) -> None:
        self.tempdir = TemporaryDirectory()

        self.favorites = FavoriteStore(
            Path(self.tempdir.name),
        )

        self.providers = PolicyProviders(
            favorites=self.favorites,
        )

        self.service = PolicyService(
            providers=self.providers,
        )

    def cleanup(self) -> None:
        self.tempdir.cleanup()


class PolicyServiceTests(unittest.TestCase):

    def test_service_loads_builtin_rules(self) -> None:
        fixture = ServiceFixture()
        self.addCleanup(fixture.cleanup)

        self.assertEqual(1, len(fixture.service.rules))
        self.assertIsInstance(
            fixture.service.rules[0],
            FavoriteRule,
        )

    def test_unfavorited_media_is_ignored(self) -> None:
        fixture = ServiceFixture()
        self.addCleanup(fixture.cleanup)

        decision = fixture.service.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertIsInstance(decision, PolicyDecision)
        self.assertFalse(decision.protected)
        self.assertEqual("ignore", decision.action.value)
        self.assertEqual(0, len(decision.reasons))

    def test_favorited_media_is_protected(self) -> None:
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

        self.assertTrue(decision.protected)
        self.assertEqual("protect", decision.action.value)
        self.assertEqual(1, len(decision.reasons))
        self.assertEqual(
            "favorite",
            decision.reasons[0].code,
        )

    def test_service_can_be_reused_for_multiple_evaluations(self) -> None:
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

        self.assertFalse(first_decision.protected)
        self.assertTrue(second_decision.protected)

    def test_explicit_empty_rule_set_disables_builtin_rules(self) -> None:
        fixture = ServiceFixture()
        self.addCleanup(fixture.cleanup)

        fixture.favorites.add(
            USER_A,
            "jellyfin",
            "abc123",
            media_type="movie",
        )

        service = PolicyService(
            providers=fixture.providers,
            rules=[],
        )

        decision = service.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertEqual(0, len(service.rules))
        self.assertFalse(decision.protected)
        self.assertEqual("ignore", decision.action.value)


if __name__ == "__main__":
    unittest.main()
