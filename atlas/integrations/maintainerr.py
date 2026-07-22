"""Maintainerr deletion authorization integration for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
)
from atlas.cleanup.service import CleanupService


class MaintainerrIntegrationError(ValueError):
    """Raised when a Maintainerr assessment contains invalid data."""


@dataclass(frozen=True, slots=True)
class MaintainerrAssessment:
    """Atlas authorization result for one Maintainerr deletion candidate."""

    provider: str
    item_id: str
    can_delete: bool
    decision: CleanupDecision | None = None
    error: str | None = None

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

        if not isinstance(self.can_delete, bool):
            raise MaintainerrIntegrationError(
                "can_delete must be a boolean"
            )

        if (
            self.decision is not None
            and not isinstance(
                self.decision,
                CleanupDecision,
            )
        ):
            raise MaintainerrIntegrationError(
                "decision must be a CleanupDecision"
            )

        if self.decision is not None:
            if self.decision.provider != provider:
                raise MaintainerrIntegrationError(
                    "decision provider does not match "
                    "assessment provider"
                )

            if self.decision.item_id != item_id:
                raise MaintainerrIntegrationError(
                    "decision item_id does not match "
                    "assessment item_id"
                )

            decision_allows_delete = (
                self.decision.action
                is CleanupAction.DELETE
            )

            if self.can_delete != decision_allows_delete:
                raise MaintainerrIntegrationError(
                    "can_delete must match the cleanup decision"
                )

        normalized_error = _optional_text(
            self.error,
            "error",
        )

        if self.can_delete and self.decision is None:
            raise MaintainerrIntegrationError(
                "allowed deletion requires a cleanup decision"
            )

        if self.can_delete and normalized_error is not None:
            raise MaintainerrIntegrationError(
                "allowed deletion cannot contain an error"
            )

        if self.decision is None and normalized_error is None:
            raise MaintainerrIntegrationError(
                "denied assessment without a decision "
                "must contain an error"
            )

        object.__setattr__(
            self,
            "error",
            normalized_error,
        )

    @property
    def denied(self) -> bool:
        """Return True when Maintainerr may not delete the item."""

        return not self.can_delete

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized Maintainerr assessment."""

        return {
            "provider": self.provider,
            "item_id": self.item_id,
            "can_delete": self.can_delete,
            "denied": self.denied,
            "decision": (
                self.decision.to_dict()
                if self.decision is not None
                else None
            ),
            "error": self.error,
        }


class MaintainerrIntegration:
    """Authorize Maintainerr deletion candidates through Atlas cleanup."""

    def __init__(
        self,
        cleanup_service: CleanupService | None = None,
    ) -> None:
        self._cleanup_service = (
            cleanup_service
            if cleanup_service is not None
            else CleanupService()
        )

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> MaintainerrAssessment:
        """Evaluate whether Maintainerr may delete one media item.

        Evaluation failures deny deletion so that Maintainerr cannot bypass
        Atlas policy when policy or retention state is unavailable.
        """

        normalized_provider = _required_text(
            provider,
            "provider",
        ).lower()

        normalized_item_id = _required_text(
            item_id,
            "item_id",
        )

        try:
            decision = self._cleanup_service.evaluate(
                normalized_provider,
                normalized_item_id,
            )
        except Exception as exc:
            return MaintainerrAssessment(
                provider=normalized_provider,
                item_id=normalized_item_id,
                can_delete=False,
                error=(
                    str(exc).strip()
                    or exc.__class__.__name__
                ),
            )

        if not isinstance(decision, CleanupDecision):
            return MaintainerrAssessment(
                provider=normalized_provider,
                item_id=normalized_item_id,
                can_delete=False,
                error=(
                    "cleanup service must return "
                    "a CleanupDecision"
                ),
            )

        if (
            decision.provider != normalized_provider
            or decision.item_id != normalized_item_id
        ):
            return MaintainerrAssessment(
                provider=normalized_provider,
                item_id=normalized_item_id,
                can_delete=False,
                error=(
                    "cleanup decision identity does not match "
                    "the Maintainerr candidate"
                ),
            )

        return MaintainerrAssessment(
            provider=decision.provider,
            item_id=decision.item_id,
            can_delete=(
                decision.action
                is CleanupAction.DELETE
            ),
            decision=decision,
        )


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MaintainerrIntegrationError(
            f"{field_name} is required"
        )

    return value.strip()


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise MaintainerrIntegrationError(
            f"{field_name} must be non-empty text"
        )

    return value.strip()
