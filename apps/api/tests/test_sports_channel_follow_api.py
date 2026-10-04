from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from starlette.responses import Response
from atlas_api.routes.v1.sports import create_sports_follow, remove_sports_follow
from atlas_api.schemas.sports import SportsFollowCreateRequest
from atlas_api.services.sports import SportsWriterTransportError

CHANNEL = {"id": "nfl-redzone", "atlas_channel_id": "sports-live-nfl-redzone", "name": "NFL RedZone", "standalone": True}

def service():
    result = Mock()
    result.list_live_sources.return_value = [CHANNEL]
    result.create_follow_subscription.return_value = ({"subscription_id":"sub-one", "type":"channel", "provider":"atlas", "id":CHANNEL["atlas_channel_id"], "name":"NFL RedZone", "user":"owned-user", "enabled":True, "record":False, "created_at":None}, True)
    return result

def request(**changes):
    return SportsFollowCreateRequest(**dict({"type":"channel", "provider":"atlas", "provider_id":CHANNEL["atlas_channel_id"]}, **changes))

def test_channel_follow_uses_authenticated_owner_and_catalog_only():
    api = service()
    response = Response()
    result = create_sports_follow(request(), response, SimpleNamespace(user_id="owned-user"), api)
    assert result.type == "channel" and result.record is False
    assert response.headers["cache-control"] == "no-store"
    api.create_follow_subscription.assert_called_once_with(user_id="owned-user", provider_name="atlas", subscription_type="channel", provider_id=CHANNEL["atlas_channel_id"])
    assert api.mock_calls[0][0] == "list_live_sources"
    assert len(api.mock_calls) == 2

@pytest.mark.parametrize("change,code", [({"provider":"thesportsdb"},422), ({"provider_id":"sports-live-missing"},404), ({"type":"unknown"},422)])
def test_invalid_channel_follow_never_mutates(change, code):
    api = service()
    with pytest.raises(HTTPException) as error:
        create_sports_follow(request(**change), Response(), SimpleNamespace(user_id="owned-user"), api)
    assert error.value.status_code == code
    api.create_follow_subscription.assert_not_called()

def test_duplicate_channel_follow_is_200():
    api = service()
    api.create_follow_subscription.return_value = (api.create_follow_subscription.return_value[0], False)
    response = Response()
    create_sports_follow(request(), response, SimpleNamespace(user_id="owned-user"), api)
    assert response.status_code == 200

def test_catalog_failure_is_not_empty_and_does_not_leak_backend_detail():
    api = service()
    api.list_live_sources.side_effect = SportsWriterTransportError("secret-private-url")
    with pytest.raises(HTTPException) as error:
        create_sports_follow(request(), Response(), SimpleNamespace(user_id="owned-user"), api)
    assert error.value.status_code == 503 and "secret" not in error.value.detail
    api.create_follow_subscription.assert_not_called()

def test_unfollow_preserves_authenticated_user_scope():
    api = service()
    api.remove_follow_subscription.return_value = False
    with pytest.raises(HTTPException) as error:
        remove_sports_follow("sub-other", SimpleNamespace(user_id="owned-user"), api)
    assert error.value.status_code == 404
    api.remove_follow_subscription.assert_called_once_with(user_id="owned-user", subscription_id="sub-other")
