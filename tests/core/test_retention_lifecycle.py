"""Retention deletion-lifecycle contracts for Project Atlas v1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from atlas.dislikes import DislikeStore
from atlas.favorites import FavoriteStore
from atlas.policies import (
    PolicyDecision,
    PolicyService,
)
from atlas.policies.providers import PolicyProviders
from atlas.retention import (
    RetentionDecision,
    RetentionLifecycle,
    RetentionLifecycleRule,
    RetentionLifecycleState,
    RetentionService,
)


NOW = datetime(
    2026,
    9,
    2,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

USER_A = "usr_" + ("a" * 32)
USER_B = "usr_" + ("b" * 32)


class StubPolicyService:
    """Return a normalized unprotected policy decision."""

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            provider=provider,
            item_id=item_id,
            action="ignore",
        )


class StubUserStore:
    """Return controlled Atlas/Jellyfin user profiles."""

    def __init__(
        self,
        profiles: list[dict[str, object]],
    ) -> None:
        self.profiles = profiles

    def list_users(self) -> list[dict[str, object]]:
        return self.profiles


class StubRetentionProvider:
    """Return controlled provider-backed retention state."""

    def __init__(
        self,
        state: dict[str, object],
    ) -> None:
        self.state = state

    def get_retention_state(
        self,
        item_id: str,
        *,
        user_ids: tuple[str, ...],
    ) -> dict[str, object]:
        return self.state


def profile(
    jellyfin_user_id: str,
) -> dict[str, object]:
    return {
        "user_id": "usr_" + ("c" * 32),
        "status": "active",
        "jellyfin_user_id": jellyfin_user_id,
    }


def user_state(
    jellyfin_user_id: str,
    *,
    played: bool,
    position: int,
    runtime: int,
    last_played_at: str | None,
) -> dict[str, object]:
    return {
        "jellyfin_user_id": jellyfin_user_id,
        "played": played,
        "playback_position_ticks": position,
        "runtime_ticks": runtime,
        "last_played_at": last_played_at,
    }


def media_state(
    *,
    date_created: str,
    users: tuple[dict[str, object], ...],
) -> dict[str, object]:
    return {
        "media_type": "movie",
        "date_created": date_created,
        "users": users,
    }


def service_for(
    state: dict[str, object],
    *,
    profiles: list[dict[str, object]] | None = None,
) -> RetentionService:
    return RetentionService(
        policy_service=StubPolicyService(),  # type: ignore[arg-type]
        media_providers={
            "jellyfin": StubRetentionProvider(state),
        },
        user_store=StubUserStore(
            profiles
            if profiles is not None
            else [profile(USER_A)]
        ),
        clock=lambda: NOW,
    )


def test_lifecycle_normalizes_and_serializes_timestamp_contract() -> None:
    lifecycle = RetentionLifecycle(
        state=RetentionLifecycleState.SCHEDULED,
        rule=RetentionLifecycleRule.UNWATCHED_30D,
        basis_at="2026-08-03T00:00:00+00:00",
        delete_at="2026-09-02T00:00:00+00:00",
    )

    assert lifecycle.state is RetentionLifecycleState.SCHEDULED
    assert lifecycle.rule is RetentionLifecycleRule.UNWATCHED_30D
    assert lifecycle.basis_at == "2026-08-03T00:00:00Z"
    assert lifecycle.delete_at == "2026-09-02T00:00:00Z"

    assert lifecycle.to_dict() == {
        "state": "scheduled",
        "rule": "unwatched_30d",
        "basis_at": "2026-08-03T00:00:00Z",
        "delete_at": "2026-09-02T00:00:00Z",
    }


def test_existing_retention_constructor_gets_legacy_unknown_lifecycle() -> None:
    policy = PolicyDecision(
        provider="jellyfin",
        item_id="movie-1",
        action="ignore",
    )

    decision = RetentionDecision(
        provider="jellyfin",
        item_id="movie-1",
        eligible=True,
        policy=policy,
    )

    assert decision.lifecycle.state is RetentionLifecycleState.UNKNOWN
    assert decision.lifecycle.rule is RetentionLifecycleRule.LEGACY
    assert decision.lifecycle.basis_at is None
    assert decision.lifecycle.delete_at is None

    assert decision.to_dict()["lifecycle"] == {
        "state": "unknown",
        "rule": "legacy",
        "basis_at": None,
        "delete_at": None,
    }


def test_unwatched_movie_exposes_30_day_schedule() -> None:
    service = service_for(
        media_state(
            date_created="2026-08-10T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=False,
                    position=0,
                    runtime=1000,
                    last_played_at=None,
                ),
            ),
        )
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is False
    assert decision.lifecycle.state is RetentionLifecycleState.SCHEDULED
    assert decision.lifecycle.rule is RetentionLifecycleRule.UNWATCHED_30D
    assert decision.lifecycle.basis_at == "2026-08-10T00:00:00Z"
    assert decision.lifecycle.delete_at == "2026-09-09T00:00:00Z"


def test_unwatched_movie_at_boundary_exposes_same_deadline_as_eligible() -> None:
    service = service_for(
        media_state(
            date_created="2026-08-03T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=False,
                    position=0,
                    runtime=1000,
                    last_played_at=None,
                ),
            ),
        )
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is True
    assert decision.lifecycle.state is RetentionLifecycleState.ELIGIBLE
    assert decision.lifecycle.rule is RetentionLifecycleRule.UNWATCHED_30D
    assert decision.lifecycle.basis_at == "2026-08-03T00:00:00Z"
    assert decision.lifecycle.delete_at == "2026-09-02T00:00:00Z"


def test_completed_movie_uses_latest_started_user_last_played_at() -> None:
    service = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=True,
                    position=1000,
                    runtime=1000,
                    last_played_at="2026-08-20T00:00:00Z",
                ),
                user_state(
                    USER_B,
                    played=True,
                    position=940,
                    runtime=1000,
                    last_played_at="2026-09-01T00:00:00Z",
                ),
            ),
        ),
        profiles=[
            profile(USER_A),
            profile(USER_B),
        ],
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is False
    assert decision.lifecycle.state is RetentionLifecycleState.SCHEDULED
    assert decision.lifecycle.rule is RetentionLifecycleRule.WATCHED_72H
    assert decision.lifecycle.basis_at == "2026-09-01T00:00:00Z"
    assert decision.lifecycle.delete_at == "2026-09-04T00:00:00Z"


def test_completed_movie_at_72_hour_boundary_is_eligible_with_deadline() -> None:
    service = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=True,
                    position=940,
                    runtime=1000,
                    last_played_at="2026-08-30T00:00:00Z",
                ),
            ),
        )
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is True
    assert decision.lifecycle.state is RetentionLifecycleState.ELIGIBLE
    assert decision.lifecycle.rule is RetentionLifecycleRule.WATCHED_72H
    assert decision.lifecycle.basis_at == "2026-08-30T00:00:00Z"
    assert decision.lifecycle.delete_at == "2026-09-02T00:00:00Z"


def test_incomplete_started_user_has_unknown_lifecycle_and_no_deadline() -> None:
    service = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=False,
                    position=930,
                    runtime=1000,
                    last_played_at="2026-08-20T00:00:00Z",
                ),
            ),
        )
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is False
    assert decision.lifecycle.state is RetentionLifecycleState.UNKNOWN
    assert decision.lifecycle.rule is RetentionLifecycleRule.UNAVAILABLE
    assert decision.lifecycle.delete_at is None


def test_favorite_policy_protection_has_no_deletion_deadline() -> None:
    with TemporaryDirectory() as root:
        favorites = FavoriteStore(Path(root))

        favorites.add(
            USER_A,
            "jellyfin",
            "movie-1",
            media_type="movie",
            title="Arrival",
        )

        service = RetentionService(
            policy_service=PolicyService(
                providers=PolicyProviders(
                    favorites=favorites,
                )
            ),
            clock=lambda: NOW,
        )

        decision = service.evaluate(
            "jellyfin",
            "movie-1",
        )

        assert decision.eligible is False
        assert decision.lifecycle.state is RetentionLifecycleState.PROTECTED
        assert (
            decision.lifecycle.rule
            is RetentionLifecycleRule.POLICY_PROTECTED
        )
        assert decision.lifecycle.basis_at is None
        assert decision.lifecycle.delete_at is None


def test_dislike_under_24_hours_exposes_accelerated_schedule() -> None:
    with TemporaryDirectory() as root:
        created_at = (
            NOW
            - timedelta(hours=23)
        )

        store = DislikeStore(
            Path(root),
            clock=lambda: created_at,
        )

        store.add(
            USER_A,
            "jellyfin",
            "movie-1",
            media_type="movie",
            title="Arrival",
        )

        service = RetentionService(
            policy_service=StubPolicyService(),  # type: ignore[arg-type]
            dislike_store=store,
            clock=lambda: NOW,
        )

        decision = service.evaluate(
            "jellyfin",
            "movie-1",
        )

        assert decision.eligible is False
        assert decision.lifecycle.state is RetentionLifecycleState.SCHEDULED
        assert decision.lifecycle.rule is RetentionLifecycleRule.DISLIKED_24H
        assert decision.lifecycle.basis_at == "2026-09-01T01:00:00Z"
        assert decision.lifecycle.delete_at == "2026-09-02T01:00:00Z"


def test_dislike_at_24_hours_is_eligible_with_same_deadline() -> None:
    with TemporaryDirectory() as root:
        created_at = (
            NOW
            - timedelta(hours=24)
        )

        store = DislikeStore(
            Path(root),
            clock=lambda: created_at,
        )

        store.add(
            USER_A,
            "jellyfin",
            "movie-1",
            media_type="movie",
            title="Arrival",
        )

        service = RetentionService(
            policy_service=StubPolicyService(),  # type: ignore[arg-type]
            dislike_store=store,
            clock=lambda: NOW,
        )

        decision = service.evaluate(
            "jellyfin",
            "movie-1",
        )

        assert decision.eligible is True
        assert decision.lifecycle.state is RetentionLifecycleState.ELIGIBLE
        assert decision.lifecycle.rule is RetentionLifecycleRule.DISLIKED_24H
        assert decision.lifecycle.basis_at == "2026-09-01T00:00:00Z"
        assert decision.lifecycle.delete_at == "2026-09-02T00:00:00Z"


def test_legacy_service_preserves_eligibility_without_fake_deadline() -> None:
    service = RetentionService(
        policy_service=StubPolicyService(),  # type: ignore[arg-type]
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is True
    assert decision.lifecycle.state is RetentionLifecycleState.UNKNOWN
    assert decision.lifecycle.rule is RetentionLifecycleRule.LEGACY
    assert decision.lifecycle.basis_at is None
    assert decision.lifecycle.delete_at is None
