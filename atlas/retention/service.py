"""High-level media-retention service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from atlas.media.jellyfin import default_jellyfin_provider
from atlas.policies import PolicyService
from atlas.retention.models import RetentionDecision
from atlas.user_profiles import default_store as default_user_store


UNWATCHED_RETENTION = timedelta(days=30)
COMPLETED_RETENTION = timedelta(hours=72)
COMPLETION_THRESHOLD = 0.94


class RetentionMediaProvider(Protocol):
    """Provider surface required for retention-state evaluation."""

    def get_retention_state(
        self,
        item_id: str,
        *,
        user_ids: tuple[str, ...],
    ) -> Mapping[str, object]:
        """Return normalized retention metadata for one media item."""


class RetentionUserStore(Protocol):
    """User-profile surface required by retention evaluation."""

    def list_users(self) -> list[dict[str, Any]]:
        """Return Atlas user profiles."""


class RetentionService:
    """Stable interface for media-removal eligibility decisions."""

    def __init__(
        self,
        policy_service: PolicyService | None = None,
        *,
        media_providers: Mapping[
            str,
            RetentionMediaProvider,
        ]
        | None = None,
        user_store: RetentionUserStore | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.policy_service = (
            policy_service
            if policy_service is not None
            else PolicyService()
        )

        self.media_providers = (
            {
                str(name).strip().lower(): provider
                for name, provider in media_providers.items()
                if str(name).strip()
            }
            if media_providers is not None
            else None
        )

        self.user_store = user_store
        self.clock = (
            clock
            if clock is not None
            else lambda: datetime.now(timezone.utc)
        )

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> RetentionDecision:
        """Evaluate whether one provider media item may be removed."""

        policy = self.policy_service.evaluate(
            provider,
            item_id,
        )

        if policy.protected:
            return RetentionDecision(
                provider=policy.provider,
                item_id=policy.item_id,
                eligible=False,
                policy=policy,
            )

        # Preserve the established service contract for callers that have
        # not yet opted into provider-backed timing semantics. Production
        # wiring is introduced separately after this contract is certified.
        if (
            self.media_providers is None
            or self.user_store is None
        ):
            return RetentionDecision(
                provider=policy.provider,
                item_id=policy.item_id,
                eligible=True,
                policy=policy,
            )

        eligible = self._timing_eligibility(
            policy.provider,
            policy.item_id,
        )

        return RetentionDecision(
            provider=policy.provider,
            item_id=policy.item_id,
            eligible=eligible,
            policy=policy,
        )

    def _timing_eligibility(
        self,
        provider: str,
        item_id: str,
    ) -> bool:
        """Return timing eligibility, failing closed on ambiguity."""

        try:
            media_provider = self.media_providers[provider]
        except (KeyError, TypeError):
            return False

        try:
            user_ids = self._active_linked_user_ids()
            state = media_provider.get_retention_state(
                item_id,
                user_ids=user_ids,
            )
        except Exception:
            return False

        if not isinstance(state, Mapping):
            return False

        media_type = state.get("media_type")

        if (
            not isinstance(media_type, str)
            or media_type.strip().lower() != "movie"
        ):
            return False

        created_at = _timestamp_or_none(
            state.get("date_created")
        )

        if created_at is None:
            return False

        now = self._now_or_none()

        if now is None:
            return False

        if created_at > now:
            return False

        users = state.get("users")

        if not isinstance(users, (tuple, list)):
            return False

        parsed_users: list[_UserWatchState] = []

        seen_user_ids: set[str] = set()

        for raw_user in users:
            parsed = _parse_user_watch_state(raw_user)

            if parsed is None:
                return False

            if parsed.jellyfin_user_id in seen_user_ids:
                return False

            seen_user_ids.add(parsed.jellyfin_user_id)
            parsed_users.append(parsed)

        expected_user_ids = set(user_ids)

        if set(seen_user_ids) != expected_user_ids:
            return False

        started = [
            user
            for user in parsed_users
            if user.started
        ]

        if not started:
            return (
                now - created_at
                >= UNWATCHED_RETENTION
            )

        if any(
            user.completion_ratio
            < COMPLETION_THRESHOLD
            for user in started
        ):
            return False

        completed_at_values: list[datetime] = []

        for user in started:
            if user.last_played_at is None:
                return False

            if user.last_played_at > now:
                return False

            completed_at_values.append(
                user.last_played_at
            )

        latest_completion = max(completed_at_values)

        return (
            now - latest_completion
            >= COMPLETED_RETENTION
        )

    def _active_linked_user_ids(
        self,
    ) -> tuple[str, ...]:
        """Return active linked Jellyfin identities deterministically."""

        profiles = self.user_store.list_users()

        if not isinstance(profiles, list):
            raise TypeError(
                "user store must return a list"
            )

        linked: set[str] = set()

        for profile in profiles:
            if not isinstance(profile, Mapping):
                raise TypeError(
                    "user profile must be a mapping"
                )

            status = profile.get("status")

            if not isinstance(status, str):
                raise TypeError(
                    "user profile status is invalid"
                )

            if status.strip().lower() != "active":
                continue

            jellyfin_user_id = profile.get(
                "jellyfin_user_id"
            )

            if jellyfin_user_id is None:
                continue

            if (
                not isinstance(jellyfin_user_id, str)
                or not jellyfin_user_id.strip()
            ):
                raise TypeError(
                    "Jellyfin user ID is invalid"
                )

            linked.add(
                jellyfin_user_id.strip()
            )

        return tuple(sorted(linked))

    def _now_or_none(self) -> datetime | None:
        try:
            value = self.clock()
        except Exception:
            return None

        if not isinstance(value, datetime):
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            return None

        return value.astimezone(timezone.utc)


class _UserWatchState:
    """Validated normalized watch state used internally."""

    __slots__ = (
        "jellyfin_user_id",
        "played",
        "playback_position_ticks",
        "runtime_ticks",
        "last_played_at",
    )

    def __init__(
        self,
        *,
        jellyfin_user_id: str,
        played: bool,
        playback_position_ticks: int,
        runtime_ticks: int,
        last_played_at: datetime | None,
    ) -> None:
        self.jellyfin_user_id = jellyfin_user_id
        self.played = played
        self.playback_position_ticks = (
            playback_position_ticks
        )
        self.runtime_ticks = runtime_ticks
        self.last_played_at = last_played_at

    @property
    def started(self) -> bool:
        return self.playback_position_ticks > 0

    @property
    def completion_ratio(self) -> float:
        return (
            self.playback_position_ticks
            / self.runtime_ticks
        )


def _parse_user_watch_state(
    raw: object,
) -> _UserWatchState | None:
    if not isinstance(raw, Mapping):
        return None

    jellyfin_user_id = raw.get(
        "jellyfin_user_id"
    )
    played = raw.get("played")
    position = raw.get(
        "playback_position_ticks"
    )
    runtime = raw.get("runtime_ticks")
    last_played_raw = raw.get(
        "last_played_at"
    )

    if (
        not isinstance(jellyfin_user_id, str)
        or not jellyfin_user_id.strip()
    ):
        return None

    if not isinstance(played, bool):
        return None

    if (
        isinstance(position, bool)
        or not isinstance(position, int)
        or position < 0
    ):
        return None

    if (
        isinstance(runtime, bool)
        or not isinstance(runtime, int)
        or runtime <= 0
    ):
        return None

    if position > runtime:
        return None

    last_played_at: datetime | None

    if last_played_raw is None:
        last_played_at = None
    else:
        last_played_at = _timestamp_or_none(
            last_played_raw
        )

        if last_played_at is None:
            return None

    # Contradictory provider evidence is unsafe to interpret.
    if position == 0 and last_played_at is not None:
        return None

    return _UserWatchState(
        jellyfin_user_id=jellyfin_user_id.strip(),
        played=played,
        playback_position_ticks=position,
        runtime_ticks=runtime,
        last_played_at=last_played_at,
    )


def _timestamp_or_none(
    value: object,
) -> datetime | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    try:
        parsed = datetime.fromisoformat(
            normalized.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        return None

    return parsed.astimezone(timezone.utc)


def default_retention_service() -> RetentionService:
    """Construct the production media-retention service."""

    return RetentionService(
        media_providers={
            "jellyfin": default_jellyfin_provider(),
        },
        user_store=default_user_store(),
    )
