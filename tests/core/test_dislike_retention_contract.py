"""Behavioral RED contract for Atlas v1 Dislike retention semantics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlas.policies import (
    PolicyAction,
    PolicyDecision,
)


NOW = datetime(
    2026,
    9,
    11,
    21,
    30,
    0,
    tzinfo=timezone.utc,
)

USER_A = "usr_" + "a" * 32


class StubPolicyService:
    """Return one deterministic non-protected policy decision."""

    def __init__(
        self,
        *,
        protected: bool = False,
    ) -> None:
        self.protected = protected

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> PolicyDecision:
        provider = provider.strip().lower()
        item_id = item_id.strip()

        if not self.protected:
            return PolicyDecision(
                provider=provider,
                item_id=item_id,
                action=PolicyAction.IGNORE,
            )

        from atlas.policies import PolicyReason

        return PolicyDecision(
            provider=provider,
            item_id=item_id,
            action=PolicyAction.PROTECT,
            reasons=(
                PolicyReason(
                    code="favorite",
                    source="atlas.favorites",
                    detail=(
                        "One or more Atlas users "
                        "favorited this item."
                    ),
                ),
            ),
        )


def _imports():
    """Import RED surfaces only inside tests."""

    from atlas.dislikes import DislikeStore
    from atlas.retention import RetentionService

    return DislikeStore, RetentionService


def _store(
    root: Path,
    *,
    created_at: datetime,
):
    DislikeStore, _ = _imports()

    return DislikeStore(
        root,
        clock=lambda: created_at,
    )


def _service(
    store,
    *,
    protected: bool = False,
):
    _, RetentionService = _imports()

    return RetentionService(
        policy_service=StubPolicyService(
            protected=protected,
        ),
        dislike_store=store,
        clock=lambda: NOW,
    )


def test_dislike_under_24_hours_is_retained(
    tmp_path: Path,
) -> None:
    """Dislike requests cleanup, but not before its 24-hour window."""

    store = _store(
        tmp_path,
        created_at=(
            NOW
            - timedelta(hours=24)
            + timedelta(seconds=1)
        ),
    )

    store.add(
        USER_A,
        "jellyfin",
        "movie-1",
        media_type="movie",
        title="Arrival",
    )

    decision = _service(
        store
    ).evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is False
    assert decision.retained is True


def test_dislike_at_exactly_24_hours_is_cleanup_eligible(
    tmp_path: Path,
) -> None:
    """The accelerated Dislike boundary is inclusive at 24 hours."""

    store = _store(
        tmp_path,
        created_at=(
            NOW
            - timedelta(hours=24)
        ),
    )

    store.add(
        USER_A,
        "jellyfin",
        "movie-1",
        media_type="movie",
        title="Arrival",
    )

    decision = _service(
        store
    ).evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is True
    assert decision.retained is False


def test_removing_dislike_cancels_accelerated_eligibility(
    tmp_path: Path,
) -> None:
    """Removing the last Dislike restores ordinary retention behavior."""

    store = _store(
        tmp_path,
        created_at=(
            NOW
            - timedelta(hours=23)
        ),
    )

    record = store.add(
        USER_A,
        "jellyfin",
        "movie-1",
        media_type="movie",
        title="Arrival",
    )

    accelerated = _service(
        store
    ).evaluate(
        "jellyfin",
        "movie-1",
    )

    # A Dislike younger than 24 hours is still waiting for
    # its accelerated cleanup boundary.
    assert accelerated.eligible is False
    assert accelerated.retained is True

    store.remove(
        record["dislike_id"]
    )

    assert [
        dislike
        for dislike in store.list(
            provider="jellyfin",
        )
        if dislike["item_id"] == "movie-1"
    ] == []

    restored = _service(
        store
    ).evaluate(
        "jellyfin",
        "movie-1",
    )

    # With the Dislike gone, this exact fixture returns to the
    # established RetentionService ordinary fallback contract.
    assert restored.eligible is True
    assert restored.retained is False


def test_favorite_protection_wins_over_mature_dislike(
    tmp_path: Path,
) -> None:
    """A Favorite remains an absolute protection against auto-cleanup."""

    store = _store(
        tmp_path,
        created_at=(
            NOW
            - timedelta(hours=48)
        ),
    )

    store.add(
        USER_A,
        "jellyfin",
        "movie-1",
        media_type="movie",
        title="Arrival",
    )

    decision = _service(
        store,
        protected=True,
    ).evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is False
    assert decision.retained is True
    assert decision.policy.protected is True
    assert (
        decision.policy.reasons[0].code
        == "favorite"
    )


def test_dislikes_are_user_scoped_but_media_lookup_is_shared(
    tmp_path: Path,
) -> None:
    """Records retain owner identity while retention resolves media identity."""

    store = _store(
        tmp_path,
        created_at=(
            NOW
            - timedelta(hours=24)
        ),
    )

    record = store.add(
        USER_A,
        "jellyfin",
        "movie-1",
        media_type="movie",
        title="Arrival",
    )

    assert record["user_id"] == USER_A

    owned = store.list(
        user_id=USER_A,
    )

    assert len(owned) == 1
    assert owned[0]["dislike_id"] == record["dislike_id"]

    matching = [
        dislike
        for dislike in store.list(
            provider="jellyfin",
        )
        if dislike["item_id"] == "movie-1"
    ]

    assert len(matching) == 1
    assert matching[0]["user_id"] == USER_A
