"""Normalized media-retention decisions for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from atlas.policies.models import PolicyDecision


class RetentionError(ValueError):
    """Raised when a retention model contains invalid data."""


class RetentionLifecycleState(str, Enum):
    """Current deletion-lifecycle state for one retained media item."""

    PROTECTED = "protected"
    SCHEDULED = "scheduled"
    ELIGIBLE = "eligible"
    UNKNOWN = "unknown"


class RetentionLifecycleRule(str, Enum):
    """Rule responsible for one deletion-lifecycle decision."""

    POLICY_PROTECTED = "policy_protected"
    DISLIKED_24H = "disliked_24h"
    WATCHED_72H = "watched_72h"
    UNWATCHED_30D = "unwatched_30d"
    LEGACY = "legacy"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RetentionLifecycle:
    """Normalized deletion schedule information for one media item."""

    state: RetentionLifecycleState
    rule: RetentionLifecycleRule
    basis_at: str | None = None
    delete_at: str | None = None

    def __post_init__(self) -> None:
        try:
            state = (
                self.state
                if isinstance(self.state, RetentionLifecycleState)
                else RetentionLifecycleState(self.state)
            )
        except (TypeError, ValueError) as exc:
            raise RetentionError(
                f"invalid retention lifecycle state: {self.state}"
            ) from exc

        try:
            rule = (
                self.rule
                if isinstance(self.rule, RetentionLifecycleRule)
                else RetentionLifecycleRule(self.rule)
            )
        except (TypeError, ValueError) as exc:
            raise RetentionError(
                f"invalid retention lifecycle rule: {self.rule}"
            ) from exc

        object.__setattr__(self, "state", state)
        object.__setattr__(self, "rule", rule)
        object.__setattr__(
            self,
            "basis_at",
            _optional_timestamp(
                self.basis_at,
                "basis_at",
            ),
        )
        object.__setattr__(
            self,
            "delete_at",
            _optional_timestamp(
                self.delete_at,
                "delete_at",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized deletion lifecycle."""

        return {
            "state": self.state.value,
            "rule": self.rule.value,
            "basis_at": self.basis_at,
            "delete_at": self.delete_at,
        }


def _legacy_lifecycle() -> RetentionLifecycle:
    """Return the backward-compatible lifecycle for legacy constructors."""

    return RetentionLifecycle(
        state=RetentionLifecycleState.UNKNOWN,
        rule=RetentionLifecycleRule.LEGACY,
    )


@dataclass(frozen=True)
class RetentionDecision:
    """Final retention eligibility decision for one provider media item."""

    provider: str
    item_id: str
    eligible: bool
    policy: PolicyDecision
    lifecycle: RetentionLifecycle = field(
        default_factory=_legacy_lifecycle,
    )
    evaluated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        provider = _required_text(
            self.provider,
            "provider",
        ).lower()

        item_id = _required_text(
            self.item_id,
            "item_id",
        )

        object.__setattr__(
            self,
            "provider",
            provider,
        )
        object.__setattr__(
            self,
            "item_id",
            item_id,
        )

        if not isinstance(self.eligible, bool):
            raise RetentionError("eligible must be a boolean")

        if not isinstance(self.policy, PolicyDecision):
            raise RetentionError(
                "policy must be a PolicyDecision",
            )

        if not isinstance(self.lifecycle, RetentionLifecycle):
            raise RetentionError(
                "lifecycle must be a RetentionLifecycle",
            )

        if self.policy.provider != provider:
            raise RetentionError(
                "policy provider does not match retention provider",
            )

        if self.policy.item_id != item_id:
            raise RetentionError(
                "policy item_id does not match retention item_id",
            )

        object.__setattr__(
            self,
            "evaluated_at",
            _required_timestamp(
                self.evaluated_at,
                "evaluated_at",
            ),
        )

    @property
    def retained(self) -> bool:
        """Return whether Atlas must retain the media item."""

        return not self.eligible

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized retention decision."""

        return {
            "provider": self.provider,
            "item_id": self.item_id,
            "eligible": self.eligible,
            "retained": self.retained,
            "policy": self.policy.to_dict(),
            "lifecycle": self.lifecycle.to_dict(),
            "evaluated_at": self.evaluated_at,
        }


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetentionError(
            f"{field_name} is required",
        )

    return value.strip()


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise RetentionError(
            f"{field_name} must be an ISO-8601 timestamp or null",
        )

    return _required_timestamp(
        value,
        field_name,
    )


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetentionError(
            f"{field_name} is required",
        )

    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00"),
        )
    except ValueError as exc:
        raise RetentionError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise RetentionError(
            f"{field_name} must include a timezone",
        )

    return (
        parsed
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _now_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
