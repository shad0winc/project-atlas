"""Fixture proof that policy and owner selection cannot use separate logins."""

import importlib.util
import json
import sys
import types
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
for package in ("apps", "apps.m3u", "apps.proxy", "apps.proxy.live_proxy"):
    module = types.ModuleType(package)
    module.__path__ = []
    sys.modules.setdefault(package, module)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ledger = load("apps.m3u.reservation_ledger", "apps/m3u/reservation_ledger.py")
plan_module = load("apps.m3u.verified_live_plan", "apps/m3u/verified_live_plan.py")
policy_module = load("apps.m3u.verified_live_policy", "apps/m3u/verified_live_policy.py")
strict_module = load("apps.m3u.strict_effective_credentials", "apps/m3u/strict_effective_credentials.py")
adapter_module = load("apps.m3u.atlas_verified_policy_adapter", "apps/m3u/atlas_verified_policy_adapter.py")
claims_module = load("apps.m3u.atlas_policy_claims", "apps/m3u/atlas_policy_claims.py")
selection = load("apps.proxy.live_proxy.verified_selection", "apps/proxy/live_proxy/verified_selection.py")


class Query:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self

    def order_by(self, *_):
        return self.rows

    def filter(self, **_):
        return self.rows


class Claims:
    def __init__(self, claim):
        self.claim = claim

    def fetch(self, _):
        return (self.claim,)


class BoundPlanTests(unittest.TestCase):
    def setUp(self):
        self.channel_id = str(uuid.uuid4())
        self.profile = SimpleNamespace(id=21, m3u_account_id=31,
                                       max_streams=1, is_active=True, is_default=True)
        self.account = SimpleNamespace(id=31, account_type="XC", is_active=True,
            max_streams=1, profiles=Query([self.profile]),
            get_user_agent_string=lambda: "test-agent")
        self.stream = SimpleNamespace(id=11, stream_id="1234", m3u_account_id=31,
                                      m3u_account=self.account)
        output = SimpleNamespace(id=41, is_proxy=lambda: True,
                                 is_redirect=lambda: False)
        self.channel = SimpleNamespace(uuid=uuid.UUID(self.channel_id),
            streams=Query([self.stream]), get_stream_profile=lambda: output)
        self.claim = SimpleNamespace(channel_uuid=self.channel_id,
            source_id="source-1", account_id=31, configured_max_connections=1,
            credential_realm="evestv")
        self.credentials = ("https://provider.invalid", "verified-user", "private-password")

    def adapter(self, credentials=None):
        return adapter_module.AtlasVerifiedPolicyAdapter(
            claim_client=Claims(self.claim),
            capacity_reader=lambda account, identity:
                adapter_module.ProviderCapacityEvidence(31, "active", 1, 0, 1000),
            transformed_credentials=lambda account, profile:
                self.credentials if credentials is None else credentials,
            scope_key=b"server-held-test-key-000000000000000001",
            now_unix=1001,
        )

    def test_one_identity_builds_scope_and_private_url(self):
        selected = self.adapter()(self.channel, self.stream, self.profile,
                                  self.account, "lease-1")
        self.assertIsInstance(selected, plan_module.VerifiedLivePlan)
        self.assertEqual(selected.upstream_url,
            "https://provider.invalid/live/verified-user/private-password/1234.ts")
        self.assertNotIn("private-password", repr(selected))
        with patch.object(selection, "reserve_live_channel", return_value=("b" * 32, 1)):
            handle = selection.select_verified_channel(object(), channel=self.channel,
                owner_lease="lease-1", policy=self.adapter())
        self.assertEqual(handle.stream_url, selected.upstream_url)
        self.assertEqual(handle.spec.credential_scope, selected.spec.credential_scope)
        self.assertNotIn("private-password", repr(handle))

    def test_exact_atlas_wire_claim_drives_selected_policy(self):
        row = dict(channel_uuid=self.channel_id, source_id="source-1",
                   account_id=31, configured_max_connections=1,
                   credential_realm="evestv", provider="thesportsdb",
                   provider_event_id="2475416")

        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self, limit):
                return json.dumps({"claims": [row]}).encode()[:limit]

        opener = SimpleNamespace(open=lambda request, timeout: Response())
        client = claims_module.AtlasPolicyClaimClient(
            origin="http://atlas-sports-controller:9000",
            token="server-held-test-token-0123456789012345", opener=opener,
        )
        adapter = self.adapter()
        adapter.claim_client = client
        plan = adapter(self.channel, self.stream, self.profile,
                       self.account, "lease-1")
        self.assertEqual(plan.spec.profile_capacity, 1)
        self.assertEqual(plan.upstream_url,
            "https://provider.invalid/live/verified-user/private-password/1234.ts")

    def test_bad_stream_identity_refuses_before_reservation(self):
        self.stream.stream_id = "1234/other"
        with patch.object(selection, "reserve_live_channel") as reserve:
            with self.assertRaises(policy_module.VerifiedLivePolicyUnavailable):
                selection.select_verified_channel(object(), channel=self.channel,
                    owner_lease="lease-1", policy=self.adapter())
        reserve.assert_not_called()

    def test_no_separate_resolver_and_no_untrusted_spec(self):
        def bare_spec(*args):
            return self.adapter()(*args).spec
        with patch.object(selection, "reserve_live_channel") as reserve:
            with self.assertRaises(selection.VerifiedSelectionError):
                selection.select_verified_channel(object(), channel=self.channel,
                    owner_lease="lease-1", policy=bare_spec)
            with self.assertRaises(TypeError):
                selection.select_verified_channel(object(), channel=self.channel,
                    owner_lease="lease-1", policy=self.adapter(),
                    resolve_url=lambda *_: "http://fallback.invalid/live/other")
        reserve.assert_not_called()

    def test_setup_failure_releases_only_pending_token(self):
        self.account.get_user_agent_string = lambda: (_ for _ in ()).throw(
            RuntimeError("sensitive transport details"))
        with patch.object(selection, "reserve_live_channel", return_value=("b" * 32, 1)), \
             patch.object(selection, "release_pending_live_channel", return_value=True) as release:
            with self.assertRaises(selection.VerifiedSelectionError) as caught:
                selection.select_verified_channel(object(), channel=self.channel,
                    owner_lease="lease-1", policy=self.adapter())
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertEqual(release.call_args.args[2], "b" * 32)

    def test_selected_viewer_policy_rechecks_model_membership(self):
        class SelectedQuery:
            def __init__(self, row, conditions=None):
                self.row = row
                self.conditions = conditions or {}
            def filter(self, **conditions):
                return SelectedQuery(self.row, dict(self.conditions, **conditions))
            def select_related(self, *_):
                return self
            def get(self, **conditions):
                if not all(getattr(self.row, key) == value
                           for key, value in dict(self.conditions, **conditions).items()):
                    raise LookupError("selected identity unavailable")
                return self.row

        self.channel.streams = SelectedQuery(self.stream)
        self.account.profiles = SelectedQuery(self.profile)
        channel_module = types.ModuleType("apps.channels.models")
        channel_module.Channel = SimpleNamespace(objects=SimpleNamespace(
            get=lambda **kwargs: self.channel))
        with patch.dict(sys.modules, {
                "apps.channels": types.ModuleType("apps.channels"),
                "apps.channels.models": channel_module}):
            spec = self.adapter().spec_for_selected(
                self.channel_id, 11, 21, 31, "lease-1")
            owner_spec = self.adapter()(self.channel, self.stream,
                                        self.profile, self.account, "lease-1").spec
            self.assertEqual(spec.credential_scope, owner_spec.credential_scope)
            for selected in ((99, 21, 31), (11, 99, 31), (11, 21, 99)):
                with self.assertRaises(policy_module.VerifiedLivePolicyUnavailable):
                    self.adapter().spec_for_selected(
                        self.channel_id, *selected, "lease-1")


if __name__ == "__main__":
    unittest.main()
