"""Tests for durable cleanup deletion-intent contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from atlas.cleanup.deletion_intents import (
    CleanupDeletionIntent,
)
from atlas.cleanup.models import CleanupError


EXECUTION_ID = (
    "cln_0123456789abcdef"
    "0123456789abcdef"
)
CREATED_AT = datetime(
    2026,
    9,
    9,
    23,
    30,
    tzinfo=timezone.utc,
)


def make_intent(
    **overrides: object,
) -> CleanupDeletionIntent:
    values: dict[str, object] = {
        "execution_id": EXECUTION_ID,
        "provider": "jellyfin",
        "item_id": "movie-1",
        "created_at": CREATED_AT,
    }
    values.update(overrides)

    return CleanupDeletionIntent(**values)  # type: ignore[arg-type]


def test_normalizes_identity_and_timestamp() -> None:
    intent = make_intent(
        provider=" JELLYFIN ",
        item_id=" movie-1 ",
        created_at=datetime(
            2026,
            9,
            9,
            19,
            30,
            tzinfo=timezone(
                -timedelta(hours=4)
            ),
        ),
    )

    assert intent.provider == "jellyfin"
    assert intent.item_id == "movie-1"
    assert intent.created_at == CREATED_AT


def test_requires_timezone_aware_created_at() -> None:
    with pytest.raises(
        CleanupError,
        match="created_at must be timezone-aware",
    ):
        make_intent(
            created_at=datetime(
                2026,
                9,
                9,
                23,
                30,
            )
        )


def test_rejects_empty_provider() -> None:
    with pytest.raises(
        CleanupError,
        match="provider must not be empty",
    ):
        make_intent(provider=" ")


def test_rejects_empty_item_id() -> None:
    with pytest.raises(
        CleanupError,
        match="item_id must not be empty",
    ):
        make_intent(item_id="")


def test_is_immutable() -> None:
    intent = make_intent()

    with pytest.raises(FrozenInstanceError):
        intent.item_id = "changed"  # type: ignore[misc]


def test_serializes_normalized_contract() -> None:
    assert make_intent().to_dict() == {
        "execution_id": EXECUTION_ID,
        "provider": "jellyfin",
        "item_id": "movie-1",
        "created_at": "2026-09-09T23:30:00Z",
    }
