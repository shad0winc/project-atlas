from __future__ import annotations

import unittest

from atlas.policies import (
    PolicyAction,
    PolicyDecision,
    PolicyReason,
)
from atlas.retention import (
    RetentionDecision,
    RetentionError,
)


class RetentionDecisionTests(unittest.TestCase):

    def test_eligible_decision_exposes_normalized_contract(
        self,
    ) -> None:
        policy = PolicyDecision(
            provider=" Jellyfin ",
            item_id="abc123",
            action=PolicyAction.IGNORE,
        )

        decision = RetentionDecision(
            provider=" JELLYFIN ",
            item_id=" abc123 ",
            eligible=True,
            policy=policy,
            evaluated_at="2026-07-20T04:00:00+00:00",
        )

        self.assertEqual(
            "jellyfin",
            decision.provider,
        )
        self.assertEqual(
            "abc123",
            decision.item_id,
        )
        self.assertTrue(decision.eligible)
        self.assertFalse(decision.retained)
        self.assertEqual(
            "2026-07-20T04:00:00Z",
            decision.evaluated_at,
        )

        serialized = decision.to_dict()

        self.assertEqual(
            "jellyfin",
            serialized["provider"],
        )
        self.assertEqual(
            "abc123",
            serialized["item_id"],
        )
        self.assertTrue(serialized["eligible"])
        self.assertFalse(serialized["retained"])
        self.assertEqual(
            "ignore",
            serialized["policy"]["action"],
        )

    def test_ineligible_decision_preserves_policy_reasons(
        self,
    ) -> None:
        reason = PolicyReason(
            code="favorite",
            source="favorites",
            detail="Favorited by one Atlas user.",
            metadata={
                "favorite_count": 1,
            },
        )

        policy = PolicyDecision(
            provider="jellyfin",
            item_id="abc123",
            action=PolicyAction.PROTECT,
            reasons=(reason,),
        )

        decision = RetentionDecision(
            provider="jellyfin",
            item_id="abc123",
            eligible=False,
            policy=policy,
        )

        self.assertFalse(decision.eligible)
        self.assertTrue(decision.retained)
        self.assertEqual(
            "favorite",
            decision.policy.reasons[0].code,
        )
        self.assertEqual(
            1,
            decision.to_dict()["policy"]["reasons"][0][
                "metadata"
            ]["favorite_count"],
        )

    def test_rejects_invalid_boolean_and_policy_type(
        self,
    ) -> None:
        policy = PolicyDecision(
            provider="jellyfin",
            item_id="abc123",
            action=PolicyAction.IGNORE,
        )

        with self.assertRaisesRegex(
            RetentionError,
            "eligible must be a boolean",
        ):
            RetentionDecision(
                provider="jellyfin",
                item_id="abc123",
                eligible="yes",  # type: ignore[arg-type]
                policy=policy,
            )

        with self.assertRaisesRegex(
            RetentionError,
            "policy must be a PolicyDecision",
        ):
            RetentionDecision(
                provider="jellyfin",
                item_id="abc123",
                eligible=True,
                policy={},  # type: ignore[arg-type]
            )

    def test_rejects_mismatched_policy_identity(
        self,
    ) -> None:
        provider_policy = PolicyDecision(
            provider="plex",
            item_id="abc123",
            action=PolicyAction.IGNORE,
        )

        with self.assertRaisesRegex(
            RetentionError,
            "policy provider does not match",
        ):
            RetentionDecision(
                provider="jellyfin",
                item_id="abc123",
                eligible=True,
                policy=provider_policy,
            )

        item_policy = PolicyDecision(
            provider="jellyfin",
            item_id="different",
            action=PolicyAction.IGNORE,
        )

        with self.assertRaisesRegex(
            RetentionError,
            "policy item_id does not match",
        ):
            RetentionDecision(
                provider="jellyfin",
                item_id="abc123",
                eligible=True,
                policy=item_policy,
            )

    def test_rejects_invalid_identity_and_timestamp(
        self,
    ) -> None:
        policy = PolicyDecision(
            provider="jellyfin",
            item_id="abc123",
            action=PolicyAction.IGNORE,
        )

        with self.assertRaisesRegex(
            RetentionError,
            "provider is required",
        ):
            RetentionDecision(
                provider=" ",
                item_id="abc123",
                eligible=True,
                policy=policy,
            )

        with self.assertRaisesRegex(
            RetentionError,
            "evaluated_at must include a timezone",
        ):
            RetentionDecision(
                provider="jellyfin",
                item_id="abc123",
                eligible=True,
                policy=policy,
                evaluated_at="2026-07-20T04:00:00",
            )


if __name__ == "__main__":
    unittest.main()
