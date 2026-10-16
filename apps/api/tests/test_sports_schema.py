"""Contract tests for the Atlas v1 Sports HTTP schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from atlas_api.schemas.sports import (
    SportsEventResponse,
    SportsSubscriptionCreateRequest,
    SportsSubscriptionResponse,
)


def test_sports_event_response_preserves_provider_event_identity() -> None:
    event = SportsEventResponse(
        provider=" thesportsdb ",
        provider_event_id=" event-001 ",
        name=" Atlas United vs Atlas City ",
        sport=" Soccer ",
        league=" Atlas Test League ",
        start_at="2026-08-17T20:00:00Z",
        status=" scheduled ",
        requested=False,
    )

    assert event.provider == "thesportsdb"
    assert event.provider_event_id == "event-001"
    assert event.name == "Atlas United vs Atlas City"
    assert event.sport == "Soccer"
    assert event.league == "Atlas Test League"
    assert event.status == "scheduled"
    assert event.requested is False


def test_sports_subscription_create_request_accepts_only_provider_identity() -> None:
    request = SportsSubscriptionCreateRequest(
        provider=" thesportsdb ",
        provider_event_id=" event-001 ",
    )

    assert request.provider == "thesportsdb"
    assert request.provider_event_id == "event-001"


@pytest.mark.parametrize(
    "field",
    (
        "user_id",
        "subscription_id",
        "type",
        "name",
        "created_at",
        "enabled",
    ),
)
def test_sports_subscription_create_request_rejects_server_owned_fields(
    field: str,
) -> None:
    payload: dict[str, object] = {
        "provider": "thesportsdb",
        "provider_event_id": "event-001",
        field: "caller-controlled",
    }

    with pytest.raises(ValidationError):
        SportsSubscriptionCreateRequest(**payload)


@pytest.mark.parametrize(
    ("provider", "provider_event_id"),
    (
        ("", "event-001"),
        ("   ", "event-001"),
        ("thesportsdb", ""),
        ("thesportsdb", "   "),
    ),
)
def test_sports_subscription_create_request_rejects_empty_identity(
    provider: str,
    provider_event_id: str,
) -> None:
    with pytest.raises(ValidationError):
        SportsSubscriptionCreateRequest(
            provider=provider,
            provider_event_id=provider_event_id,
        )


def test_sports_subscription_response_keeps_atlas_and_provider_ids_distinct() -> None:
    response = SportsSubscriptionResponse(
        subscription_id="sub-atlas-001",
        type="event",
        provider="thesportsdb",
        provider_event_id="event-001",
        name="Atlas United vs Atlas City",
        user_id="usr-atlas-001",
        enabled=True,
        created_at="2026-08-16T20:00:00Z",
    )

    assert response.subscription_id == "sub-atlas-001"
    assert response.provider_event_id == "event-001"
    assert response.subscription_id != response.provider_event_id
    assert response.user_id == "usr-atlas-001"
    assert response.type == "event"


def test_metadata_observation_requires_paired_aware_bounded_age() -> None:
    from pydantic import ValidationError
    from atlas_api.schemas.sports import SportsEventResponse
    base = dict(provider="espn", provider_event_id="football-nfl-1", name="Game", sport="Football", league="NFL", start_at="2026-10-16T12:00:00Z", status="live", requested=False)
    valid = dict(metadata_observed_at="2026-10-16T12:00:00Z", metadata_expires_at="2026-10-16T12:01:00Z")
    assert SportsEventResponse(**base, **valid).metadata_expires_at is not None
    for age in (
        dict(metadata_observed_at="2026-10-16T12:00:00Z"),
        dict(metadata_observed_at="2026-10-16T12:00:00", metadata_expires_at="2026-10-16T12:01:00Z"),
        dict(metadata_observed_at="2026-10-16T12:00:00Z", metadata_expires_at="2026-10-16T11:00:00Z"),
        dict(metadata_observed_at="2026-10-16T12:00:00Z", metadata_expires_at="2026-10-16T14:00:00Z"),
    ):
        try:
            SportsEventResponse(**base, **age)
        except ValidationError:
            pass
        else:
            raise AssertionError("Invalid metadata age accepted")
