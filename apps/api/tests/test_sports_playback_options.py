import pytest

from atlas_api.services.sports import SportsWriterTransportError
from tests.test_sports_live_playback_route import build_harness
from tests.test_sports_live_source_reader import FakeSportsWriter


def configure(harness):
    source = harness.sports.list_live_sources()[0]
    source["playback_options"] = [
        {"option_id": "primary", "atlas_channel_id": "sports-event-001", "resource_source_id": "primary-account"},
        {"option_id": "backup-1", "atlas_channel_id": "sports-event-001--backup-1", "resource_source_id": "secondary-account"},
    ]
    harness.sports.list_live_sources = lambda: [source]
    verified = []
    harness.sports.verify_live_playback_option = lambda **kwargs: verified.append(kwargs)
    harness.sports.list_live_tv_bindings = lambda: [{"atlas_channel_id": row["atlas_channel_id"], "jellyfin_item_id": "jf"} for row in source["playback_options"]]
    acquire = harness.resource_pool.acquire
    def selected_lease(**kwargs):
        lease = acquire(**kwargs)
        lease.source_id = kwargs["candidate_source_ids"][0]
        return lease
    harness.resource_pool.acquire = selected_lease
    return verified


def test_selected_option_reserves_only_its_account_and_opens_its_exact_jellyfin_binding():
    harness = build_harness()
    verified = configure(harness)
    response = harness.client.get("/api/v1/sports/live/sports-event-001/session?option=backup-1")
    assert response.status_code == 200
    assert harness.sports.binding_calls == ["sports-event-001--backup-1"]
    assert harness.resource_pool.acquire_calls[0]["candidate_source_ids"] == ("secondary-account",)
    assert harness.resource_pool.acquire_calls[0]["target_id"] == "sports-event-001"
    assert verified[0]["option"]["resource_source_id"] == "secondary-account"


def test_unspecified_choice_uses_fixed_primary_instead_of_falling_through_accounts():
    harness = build_harness()
    configure(harness)
    assert harness.client.get("/api/v1/sports/live/sports-event-001/session").status_code == 200
    assert harness.resource_pool.acquire_calls[0]["candidate_source_ids"] == ("primary-account",)


def test_changed_physical_route_fails_before_admission_or_opening():
    harness = build_harness()
    configure(harness)
    def blocked(**kwargs):
        raise SportsWriterTransportError("secret fixture must be withheld")
    harness.sports.verify_live_playback_option = blocked
    response = harness.client.get("/api/v1/sports/live/sports-event-001/session?option=backup-1")
    assert response.status_code == 503
    assert "secret" not in response.text
    assert not harness.resource_pool.acquire_calls and not harness.playback.calls


def test_a_mismatched_lease_is_released_without_opening_a_stream():
    from types import SimpleNamespace
    harness = build_harness()
    configure(harness)
    harness.resource_pool.acquire = lambda **kwargs: SimpleNamespace(lease_id="mismatch", source_id="foreign-account")
    response = harness.client.get("/api/v1/sports/live/sports-event-001/session?option=backup-1")
    assert response.status_code == 503
    assert harness.resource_pool.release_calls
    assert not harness.playback.calls


@pytest.mark.parametrize("option,code", [("backup-2", 404), ("foreign-stream", 422)])
def test_unconfigured_or_arbitrary_option_cannot_open_a_stream(option, code):
    harness = build_harness()
    configure(harness)
    response = harness.client.get(f"/api/v1/sports/live/sports-event-001/session?option={option}")
    assert response.status_code == code
    assert not harness.resource_pool.acquire_calls and not harness.playback.calls


def test_public_choices_are_bounded_and_do_not_expose_accounts_or_jellyfin_ids():
    harness = build_harness()
    configure(harness)
    response = harness.client.get("/api/v1/sports/live/sports-event-001/options")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"options": [
        {"option_id": "primary", "label": "Primary", "configured": True},
        {"option_id": "backup-1", "label": "Backup 1", "configured": True},
    ]}
    assert not harness.playback.calls and not harness.resource_pool.acquire_calls


def test_safe_source_reader_validates_option_account_and_identity():
    harness = build_harness()
    configure(harness)
    source = harness.sports.list_live_sources()[0]
    service = FakeSportsWriter({"live_sources": [source]})
    assert service.list_live_sources()[0]["playback_options"] == source["playback_options"]
    source["playback_options"][1]["resource_source_id"] = "primary-account"
    with pytest.raises(SportsWriterTransportError):
        service.list_live_sources()
