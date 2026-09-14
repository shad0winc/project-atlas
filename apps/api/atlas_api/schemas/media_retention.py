"""Authenticated single-item media-retention response contracts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict

from atlas.retention import (
    RetentionDecision,
    RetentionLifecycle,
)


class MediaRetentionLifecycleResponse(BaseModel):
    """Authoritative deletion lifecycle for one Atlas media item."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    state: str
    rule: str
    basis_at: str | None = None
    delete_at: str | None = None

    @classmethod
    def from_domain(
        cls,
        lifecycle: RetentionLifecycle,
    ) -> Self:
        """Adapt one validated retention lifecycle."""

        if not isinstance(lifecycle, RetentionLifecycle):
            raise TypeError(
                "lifecycle must be RetentionLifecycle"
            )

        return cls(
            state=lifecycle.state.value,
            rule=lifecycle.rule.value,
            basis_at=lifecycle.basis_at,
            delete_at=lifecycle.delete_at,
        )


class MediaRetentionResponse(BaseModel):
    """Authoritative retention decision for one media item."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    provider: str
    item_id: str
    eligible: bool
    retained: bool
    lifecycle: MediaRetentionLifecycleResponse

    @classmethod
    def from_domain(
        cls,
        decision: RetentionDecision,
    ) -> Self:
        """Adapt one validated authoritative retention decision."""

        if not isinstance(decision, RetentionDecision):
            raise TypeError(
                "decision must be RetentionDecision"
            )

        return cls(
            provider=decision.provider,
            item_id=decision.item_id,
            eligible=decision.eligible,
            retained=decision.retained,
            lifecycle=(
                MediaRetentionLifecycleResponse
                .from_domain(decision.lifecycle)
            ),
        )


__all__ = [
    "MediaRetentionLifecycleResponse",
    "MediaRetentionResponse",
]
