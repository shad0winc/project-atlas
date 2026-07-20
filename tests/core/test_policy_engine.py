from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from atlas.favorites import FavoriteStore
from atlas.policies import PolicyEngine, PolicyReason
from atlas.policies.engine import PolicyContext
from atlas.policies.favorites import FavoriteRule
from atlas.policies.providers import PolicyProviders
from atlas.policies.rules import builtin_rules

USER_A = "usr_" + "a" * 32
USER_B = "usr_" + "b" * 32


class EngineFixture:
    """Provides isolated policy dependencies for each test."""

    def __init__(self) -> None:
        self.tempdir = TemporaryDirectory()

        self.favorites = FavoriteStore(
            Path(self.tempdir.name),
        )

        self.providers = PolicyProviders(
            favorites=self.favorites,
        )

    def cleanup(self) -> None:
        self.tempdir.cleanup()


class DummyRule:
    """Test rule that always contributes one protection reason."""

    def evaluate(
        self,
        context: PolicyContext,
    ) -> list[PolicyReason]:
        return [
            PolicyReason(
                code="dummy",
                source="test",
                detail="Rule fired.",
            )
        ]


class EmptyRule:
    """Test rule that contributes no reasons."""

    def evaluate(
        self,
        context: PolicyContext,
    ) -> list[PolicyReason]:
        return []


class PolicyEngineTests(unittest.TestCase):

    def test_empty_engine_returns_ignore(self) -> None:
        fixture = EngineFixture()
        self.addCleanup(fixture.cleanup)

        engine = PolicyEngine(
            providers=fixture.providers,
        )

        decision = engine.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertFalse(decision.protected)
        self.assertEqual("ignore", decision.action.value)
        self.assertEqual(0, len(decision.reasons))

    def test_single_rule_protects(self) -> None:
        fixture = EngineFixture()
        self.addCleanup(fixture.cleanup)

        engine = PolicyEngine(
            providers=fixture.providers,
        )
        engine.register(DummyRule())

        decision = engine.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertTrue(decision.protected)
        self.assertEqual(1, len(decision.reasons))

    def test_multiple_rules_merge(self) -> None:
        fixture = EngineFixture()
        self.addCleanup(fixture.cleanup)

        engine = PolicyEngine(
            providers=fixture.providers,
        )
        engine.register(DummyRule())
        engine.register(DummyRule())

        decision = engine.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertEqual(2, len(decision.reasons))

    def test_empty_rule_does_not_protect(self) -> None:
        fixture = EngineFixture()
        self.addCleanup(fixture.cleanup)

        engine = PolicyEngine(
            providers=fixture.providers,
        )
        engine.register(EmptyRule())

        decision = engine.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertFalse(decision.protected)

    def test_favorite_rule_ignores_unfavorited_media(self) -> None:
        fixture = EngineFixture()
        self.addCleanup(fixture.cleanup)

        fixture.favorites.add(
            USER_A,
            "jellyfin",
            "different-item",
            media_type="movie",
        )

        engine = PolicyEngine(
            providers=fixture.providers,
        )
        engine.register(FavoriteRule())

        decision = engine.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertFalse(decision.protected)
        self.assertEqual("ignore", decision.action.value)
        self.assertEqual(0, len(decision.reasons))

    def test_favorite_rule_protects_favorited_media(self) -> None:
        fixture = EngineFixture()
        self.addCleanup(fixture.cleanup)

        fixture.favorites.add(
            USER_A,
            "jellyfin",
            "abc123",
            media_type="movie",
            title="Arrival",
        )

        engine = PolicyEngine(
            providers=fixture.providers,
        )
        engine.register(FavoriteRule())

        decision = engine.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertTrue(decision.protected)
        self.assertEqual("protect", decision.action.value)
        self.assertEqual(1, len(decision.reasons))

        reason = decision.reasons[0]

        self.assertEqual("favorite", reason.code)
        self.assertEqual("atlas.favorites", reason.source)
        self.assertEqual(1, reason.metadata["favorite_count"])
        self.assertEqual(1, reason.metadata["user_count"])
        self.assertEqual([USER_A], reason.metadata["user_ids"])

    def test_favorite_rule_combines_multiple_user_relationships(self) -> None:
        fixture = EngineFixture()
        self.addCleanup(fixture.cleanup)

        fixture.favorites.add(
            USER_A,
            "jellyfin",
            "abc123",
            media_type="movie",
        )
        fixture.favorites.add(
            USER_B,
            "jellyfin",
            "abc123",
            media_type="movie",
        )

        engine = PolicyEngine(
            providers=fixture.providers,
        )
        engine.register(FavoriteRule())

        decision = engine.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertTrue(decision.protected)
        self.assertEqual(1, len(decision.reasons))

        reason = decision.reasons[0]

        self.assertEqual(2, reason.metadata["favorite_count"])
        self.assertEqual(2, reason.metadata["user_count"])
        self.assertEqual(
            [USER_A, USER_B],
            reason.metadata["user_ids"],
        )

    def test_favorite_rule_respects_provider_boundary(self) -> None:
        fixture = EngineFixture()
        self.addCleanup(fixture.cleanup)

        fixture.favorites.add(
            USER_A,
            "sports",
            "abc123",
            media_type="sports",
        )

        engine = PolicyEngine(
            providers=fixture.providers,
        )
        engine.register(FavoriteRule())

        decision = engine.evaluate(
            "jellyfin",
            "abc123",
        )

        self.assertFalse(decision.protected)

    def test_builtin_rules_include_favorite_rule(self) -> None:
        rules = builtin_rules()

        self.assertEqual(1, len(rules))
        self.assertIsInstance(rules[0], FavoriteRule)


if __name__ == "__main__":
    unittest.main()
