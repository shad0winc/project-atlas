from __future__ import annotations

from datetime import datetime, timezone

import pytest

from atlas.policies import (
    PolicyAction,
    PolicyDecision,
)
from atlas.retention import RetentionService


NOW = datetime(
    2026,
    9,
    2,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

USER_A = "a" * 32
USER_B = "b" * 32
USER_C = "c" * 32


class StubPolicyService:
    """Return one deterministic non-protected policy decision."""

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            provider=provider.strip().lower(),
            item_id=item_id.strip(),
            action=PolicyAction.IGNORE,
        )


class StubUserStore:
    """Expose deterministic Atlas profiles to retention."""

    def __init__(
        self,
        profiles: list[dict[str, object]],
    ) -> None:
        self.profiles = profiles

    def list_users(self) -> list[dict[str, object]]:
        return list(self.profiles)


class StubRetentionProvider:
    """Return normalized provider-neutral retention state."""

    name = "jellyfin"

    def __init__(
        self,
        state: dict[str, object],
    ) -> None:
        self.state = state
        self.calls: list[
            tuple[str, tuple[str, ...]]
        ] = []

    def get_retention_state(
        self,
        item_id: str,
        *,
        user_ids: tuple[str, ...],
    ) -> dict[str, object]:
        self.calls.append(
            (
                item_id,
                user_ids,
            )
        )
        return self.state


def profile(
    jellyfin_user_id: str | None,
    *,
    status: str = "active",
) -> dict[str, object]:
    return {
        "status": status,
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
    media_type: str = "movie",
    date_created: str = "2026-08-01T00:00:00Z",
    users: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {
        "media_type": media_type,
        "date_created": date_created,
        "users": users,
    }


def service_for(
    state: dict[str, object],
    *,
    profiles: list[dict[str, object]] | None = None,
) -> tuple[
    RetentionService,
    StubRetentionProvider,
]:
    provider = StubRetentionProvider(state)

    service = RetentionService(
        policy_service=StubPolicyService(),  # type: ignore[arg-type]
        media_providers={
            "jellyfin": provider,
        },
        user_store=StubUserStore(
            profiles
            if profiles is not None
            else [
                profile(USER_A),
            ]
        ),
        clock=lambda: NOW,
    )

    return service, provider


def test_never_started_movie_under_30_days_is_retained() -> None:
    service, _ = service_for(
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
    assert decision.retained is True


def test_never_started_movie_at_30_days_is_eligible() -> None:
    service, _ = service_for(
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
    assert decision.retained is False


def test_started_incomplete_user_blocks_cleanup() -> None:
    service, _ = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=False,
                    position=930,
                    runtime=1000,
                    last_played_at="2026-08-01T00:00:00Z",
                ),
            ),
        )
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is False


def test_exactly_94_percent_is_completion_for_retention() -> None:
    service, _ = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=True,
                    position=940,
                    runtime=1000,
                    last_played_at="2026-08-29T00:00:00Z",
                ),
            ),
        )
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is True


def test_played_item_with_reset_position_fails_closed() -> None:
    """Historical completion without measurable progress is retained."""

    service, _ = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=True,
                    position=0,
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
    assert decision.retained is True


def test_completed_movie_under_72_hours_is_retained() -> None:
    service, _ = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=True,
                    position=1000,
                    runtime=1000,
                    last_played_at="2026-08-31T00:00:01Z",
                ),
            ),
        )
    )

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is False


def test_completed_movie_at_72_hours_is_eligible() -> None:
    service, _ = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=True,
                    position=1000,
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


def test_started_incomplete_user_blocks_completed_user() -> None:
    service, _ = service_for(
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
                    played=False,
                    position=500,
                    runtime=1000,
                    last_played_at="2026-08-25T00:00:00Z",
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


def test_never_started_user_does_not_block_completed_user() -> None:
    service, _ = service_for(
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
                    played=False,
                    position=0,
                    runtime=1000,
                    last_played_at=None,
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

    assert decision.eligible is True


def test_latest_completion_timestamp_controls_72_hour_window() -> None:
    service, _ = service_for(
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
                    position=1000,
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


def test_disabled_and_unlinked_profiles_are_not_queried() -> None:
    service, provider = service_for(
        media_state(
            date_created="2026-06-01T00:00:00Z",
            users=(
                user_state(
                    USER_A,
                    played=False,
                    position=0,
                    runtime=1000,
                    last_played_at=None,
                ),
            ),
        ),
        profiles=[
            profile(USER_A),
            profile(USER_B, status="disabled"),
            profile(None),
        ],
    )

    service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert provider.calls == [
        (
            "movie-1",
            (USER_A,),
        )
    ]


@pytest.mark.parametrize(
    "media_type",
    [
        "tv",
        "anime",
        "other",
    ],
)
def test_non_movie_media_fails_closed(
    media_type: str,
) -> None:
    service, _ = service_for(
        media_state(
            media_type=media_type,
            date_created="2026-01-01T00:00:00Z",
        )
    )

    decision = service.evaluate(
        "jellyfin",
        "item-1",
    )

    assert decision.eligible is False


@pytest.mark.parametrize(
    "state",
    [
        {
            "media_type": "movie",
            "users": (),
        },
        {
            "media_type": "movie",
            "date_created": "not-a-date",
            "users": (),
        },
        {
            "media_type": "movie",
            "date_created": "2026-01-01T00:00:00Z",
            "users": (
                {
                    "jellyfin_user_id": USER_A,
                    "played": False,
                    "playback_position_ticks": 1,
                    "runtime_ticks": 0,
                    "last_played_at": None,
                },
            ),
        },
    ],
)
def test_missing_or_invalid_retention_metadata_fails_closed(
    state: dict[str, object],
) -> None:
    service, _ = service_for(state)

    decision = service.evaluate(
        "jellyfin",
        "movie-1",
    )

    assert decision.eligible is False
