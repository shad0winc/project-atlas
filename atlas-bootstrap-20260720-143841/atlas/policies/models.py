"""Normalized media-policy decisions for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class PolicyError(ValueError):
    """Raised when a policy model contains invalid data."""


class PolicyAction(str, Enum):
    """Actions that may result from policy evaluation."""

    PROTECT = "protect"
    RELEASE = "release"
    IGNORE = "ignore"


@dataclass(frozen=True)
class PolicyReason:
    """One rule's explanation for a policy decision."""

    code: str
    source: str
    detail: str
    expires_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "detail", _required_text(self.detail, "detail"))
        object.__setattr__(
            self,
            "expires_at",
            _optional_timestamp(self.expires_at, "expires_at"),
        )

        if not isinstance(self.metadata, Mapping):
            raise PolicyError("metadata must be an object")

        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "source": self.source,
            "detail": self.detail,
            "expires_at": self.expires_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PolicyDecision:
    """Final normalized policy decision for one provider media item."""

    provider: str
    item_id: str
    action: PolicyAction
    reasons: tuple[PolicyReason, ...] = ()
    evaluated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider",
            _required_text(self.provider, "provider").lower(),
        )
        object.__setattr__(
            self,
            "item_id",
            _required_text(self.item_id, "item_id"),
        )

        try:
            action = (
                self.action
                if isinstance(self.action, PolicyAction)
                else PolicyAction(self.action)
            )
        except (TypeError, ValueError) as exc:
            raise PolicyError(f"invalid policy action: {self.action}") from exc

        object.__setattr__(self, "action", action)

        if not isinstance(self.reasons, tuple):
            object.__setattr__(self, "reasons", tuple(self.reasons))

        for reason in self.reasons:
            if not isinstance(reason, PolicyReason):
                raise PolicyError("reasons must contain PolicyReason values")

        object.__setattr__(
            self,
            "evaluated_at",
            _required_timestamp(self.evaluated_at, "evaluated_at"),
        )

    @property
    def protected(self) -> bool:
        return self.action is PolicyAction.PROTECT

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "item_id": self.item_id,
            "action": self.action.value,
            "protected": self.protected,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "evaluated_at": self.evaluated_at,
        }


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{field_name} is required")
    return value.strip()


def _required_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{field_name} is required")
    return _normalize_timestamp(value, field_name)


def _optional_timestamp(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{field_name} must be a timestamp or null")
    return _normalize_timestamp(value, field_name)


def _normalize_timestamp(value: str, field_name: str) -> str:
    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PolicyError(f"{field_name} must be an ISO-8601 timestamp") from exc

    if parsed.tzinfo is None:
        raise PolicyError(f"{field_name} must include a timezone")

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
