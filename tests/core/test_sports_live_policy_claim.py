from types import SimpleNamespace as Row
import unittest
from uuid import uuid4
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "modules/sports/src"))

from atlas_live_policy_claim import (
    claim_for_channel, claims_for_channel, AtlasLivePolicyUnavailable,
)


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.channel_uuid = str(uuid4())
        self.source_id = "evestv-account-2"
        self.binding = Row(atlas_channel_id="sports-live-thesportsdb-42",
                           dispatcharr_channel_uuid=self.channel_uuid)
        self.live = Row(atlas_channel_id=self.binding.atlas_channel_id,
                        resource_source_ids=(self.source_id,),
                        stream_url=f"http://dispatcharr.invalid/proxy/ts/stream/{self.channel_uuid}",
                        provider="thesportsdb", provider_event_id="42")
        self.source = Row(source_id=self.source_id, enabled=True,
                          backend_reference="dispatcharr:m3u:5", max_connections=1,
                          credential_realm="evestv")

    def claim(self, **changes):
        arguments = dict(channel_uuid=self.channel_uuid, source_id=self.source_id,
                         lifecycle_sources=(self.source,),
                         channel_bindings=(self.binding,), live_sources=(self.live,))
        arguments.update(changes)
        return claim_for_channel(**arguments)

    def test_exact_current_membership(self):
        claim = self.claim()
        self.assertEqual((claim.account_id, claim.configured_max_connections), (5, 1))
        self.assertEqual(claim.channel_uuid, self.channel_uuid)
        self.assertEqual(claim.credential_realm, "evestv")
        self.assertNotIn("stream_url", claim.to_mapping())

    def test_stale_or_ambiguous_state_fails_closed(self):
        cases = (
            dict(channel_bindings=()),
            dict(channel_bindings=(self.binding, self.binding)),
            dict(live_sources=()),
            dict(live_sources=(self.live, self.live)),
            dict(live_sources=(Row(**dict(self.live.__dict__, resource_source_ids=())),)),
            dict(live_sources=(Row(**dict(self.live.__dict__, stream_url="http://other.invalid/proxy/ts/stream/wrong")),)),
            dict(lifecycle_sources=()),
            dict(lifecycle_sources=(Row(**dict(self.source.__dict__, enabled=False)),)),
            dict(lifecycle_sources=(Row(**dict(self.source.__dict__, max_connections=0)),)),
            dict(lifecycle_sources=(Row(**dict(self.source.__dict__, credential_realm=None)),)),
            dict(lifecycle_sources=(self.source, Row(source_id="duplicate", enabled=True,
                backend_reference="5", max_connections=1, credential_realm="evestv"))),
        )
        for change in cases:
            with self.subTest(change=tuple(change)):
                with self.assertRaises(AtlasLivePolicyUnavailable):
                    self.claim(**change)

    def test_invalid_request_identity(self):
        for change in (dict(channel_uuid="bad"), dict(source_id="../bad")):
            with self.assertRaises(AtlasLivePolicyUnavailable):
                self.claim(**change)

    def test_new_source_appears_without_dispatcharr_source_id_configuration(self):
        second = Row(source_id="evestv-account-3", enabled=True,
                     backend_reference="dispatcharr:m3u:6", max_connections=1,
                     credential_realm="evestv")
        live = Row(**dict(self.live.__dict__,
                          resource_source_ids=(self.source_id, second.source_id)))
        claims = claims_for_channel(
            channel_uuid=self.channel_uuid,
            lifecycle_sources=(self.source, second),
            channel_bindings=(self.binding,), live_sources=(live,),
        )
        self.assertEqual({claim.account_id for claim in claims}, {5, 6})
        duplicate = Row(**dict(second.__dict__, backend_reference="5"))
        with self.assertRaises(AtlasLivePolicyUnavailable):
            claims_for_channel(
                channel_uuid=self.channel_uuid,
                lifecycle_sources=(self.source, duplicate),
                channel_bindings=(self.binding,), live_sources=(live,),
            )


if __name__ == "__main__":
    unittest.main()
