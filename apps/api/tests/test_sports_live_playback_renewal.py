"""The active viewer can renew their exact stream without opening a new feed."""
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas.jellyfin_live_streams import LiveStreamOwnershipError
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.core.settings import AtlasAPISettings
from atlas_api.playback_capabilities import PlaybackCapabilityError, PlaybackCapabilityService
from atlas_api.routes.v1 import sports_playback as routes

ITEM = "a" * 32
STREAM = f"/videos/{ITEM}/master.m3u8?LiveStreamId=live&PlaySessionId=play&MediaSourceId=source"


class LiveRenewalTests(unittest.TestCase):
    def setUp(self):
        self.user = AuthenticatedUser(user_id="viewer", username="viewer",
                                      display_name="Viewer", provider="test")
        self.service = PlaybackCapabilityService(AtlasAPISettings(
            jwt_secret="p" * 64, jwt_issuer="test", jwt_audience="test",
        ))
        self.playback = Mock()
        self.sessions = Mock(ttl_seconds=90)
        self.sessions.heartbeat.return_value.resource_lease_id = "resource"
        self.pool = Mock()
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides.update({
            routes.require_sports_read: lambda: self.user,
            routes.get_playback_capability_service: lambda: self.service,
            routes.get_playback_service: lambda: self.playback,
            routes.get_sports_session_registry: lambda: self.sessions,
            routes.get_sports_resource_pool: lambda: self.pool,
            routes.issue_maintenance_media_binding: lambda: "b" * 64,
        })
        self.client = TestClient(app)
        self.ticket = self.service.create_live_renewal(
            user_id="viewer", session_id="session", playable_target_id=ITEM, stream_path=STREAM,
        )

    def renew(self, session="session", ticket=None):
        return self.client.post(
            routes.router.prefix + f"/sessions/{session}/renew-playback",
            headers={"X-Atlas-Live-Renewal-Capability": ticket or self.ticket},
        )

    def test_renewal_reissues_the_same_stream_with_new_maintenance_binding(self):
        response = self.renew()
        self.assertEqual(200, response.status_code, response.text)
        claims = self.service.inspect_bootstrap(response.json()["playback_capability"])
        self.assertEqual(STREAM, claims["stream"])
        self.assertEqual("b" * 64, claims["maintenance_binding"])
        self.playback.authorize_live_stream.assert_called_once_with(
            user_id="viewer", item_id=ITEM, live_stream_id="live",
            play_session_id="play", media_source_id="source",
        )
        self.sessions.heartbeat.assert_called_once_with(session_id="session", user_id="viewer")
        self.pool.heartbeat.assert_called_once_with(lease_id="resource", user_id="viewer")
        self.playback.resolve_live_session.assert_not_called()

    def test_ticket_cannot_bootstrap_on_its_own(self):
        with self.assertRaises(PlaybackCapabilityError):
            self.service.exchange_bootstrap(self.ticket)

    def test_ticket_rejects_another_session_and_user(self):
        self.assertEqual(401, self.renew(session="other").status_code)
        self.user = AuthenticatedUser(user_id="other", username="other",
                                      display_name="Other", provider="test")
        self.assertEqual(401, self.renew().status_code)
        self.playback.authorize_live_stream.assert_not_called()
        self.sessions.heartbeat.assert_not_called()

    def test_closed_stream_cannot_be_renewed(self):
        self.playback.authorize_live_stream.side_effect = LiveStreamOwnershipError("closed")
        self.assertEqual(404, self.renew().status_code)
        self.sessions.heartbeat.assert_not_called()

    def test_direct_feed_renews_only_while_its_atlas_session_exists(self):
        stream = f"/videos/{ITEM}/master.m3u8?MediaSourceId=direct"
        ticket = self.service.create_live_renewal(
            user_id="viewer", session_id="session", playable_target_id=ITEM, stream_path=stream,
        )
        response = self.renew(ticket=ticket)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(stream, self.service.inspect_bootstrap(response.json()["playback_capability"])["stream"])
        self.playback.authorize_live_stream.assert_not_called()
        self.sessions.heartbeat.side_effect = routes.SportsSessionNotFound("expired")
        self.assertEqual(404, self.renew(ticket=ticket).status_code)
