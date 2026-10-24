"""Default-off policy adapter checks with trusted dependencies injected."""

import importlib.util
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

fixture_path = Path(__file__).resolve().parent / "test_verified_live_policy.py"
fixture_spec = importlib.util.spec_from_file_location("staged_policy_fixture", fixture_path)
fixture = importlib.util.module_from_spec(fixture_spec)
sys.modules[fixture_spec.name] = fixture
fixture_spec.loader.exec_module(fixture)

sys.modules["apps.m3u.verified_live_policy"] = fixture.policy
root = Path(__file__).resolve().parents[1]
for name in ("verified_live_plan", "strict_effective_credentials"):
    dependency_path = root / "apps/m3u" / f"{name}.py"
    dependency_spec = importlib.util.spec_from_file_location(
        f"apps.m3u.{name}", dependency_path)
    dependency = importlib.util.module_from_spec(dependency_spec)
    sys.modules[dependency_spec.name] = dependency
    dependency_spec.loader.exec_module(dependency)
path = Path(__file__).resolve().parents[1] / "apps/m3u/atlas_verified_policy_adapter.py"
spec = importlib.util.spec_from_file_location("staged_atlas_adapter", path)
adapter_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter_module
spec.loader.exec_module(adapter_module)


class Claims:
    def __init__(self, claims):
        self.claims = claims
    def fetch(self, channel_uuid):
        return self.claims


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.values = fixture.inputs()
        self.values["stream"].stream_id = "1234"
        self.claim = SimpleNamespace(
            channel_uuid=self.values["channel_id"], source_id="source-1",
            account_id=31, configured_max_connections=4,
            credential_realm="evestv",
        )
        self.evidence = adapter_module.ProviderCapacityEvidence(31, "active", 1, 0, 1000)

    def adapter(self, *, claims=None, evidence=None):
        return adapter_module.AtlasVerifiedPolicyAdapter(
            claim_client=Claims(self.claim if claims is None else claims),
            capacity_reader=lambda account, credentials: self.evidence if evidence is None else evidence,
            transformed_credentials=lambda account, profile: (
                "https://provider.example", "play-user", "private-play-password"),
            scope_key=b"server-held-test-key-000000000000000001",
            now_unix=1001,
        )

    def invoke(self, adapter):
        values = self.values
        return adapter(
            SimpleNamespace(uuid=values["channel_id"]),
            values["stream"], values["profile"], values["account"],
            values["owner_lease"],
        )

    def test_attested_capacity_and_identity(self):
        result = self.invoke(self.adapter(claims=(self.claim,)))
        self.assertEqual((result.spec.profile_capacity, result.spec.account_capacity,
                          result.spec.credential_capacity), (1, 1, 1))
        self.assertEqual(result.upstream_url,
                         "https://provider.example/live/play-user/private-play-password/1234.ts")
        self.assertNotIn("private-play-password", repr(result))

    def test_missing_realm_stale_limit_and_unrelated_account_fail_closed(self):
        variants = (
            self.adapter(claims=()),
            self.adapter(claims=(SimpleNamespace(**dict(self.claim.__dict__, credential_realm=None)),)),
            self.adapter(claims=(self.claim,), evidence=replace(self.evidence, max_connections=0)),
            self.adapter(claims=(self.claim,), evidence=replace(self.evidence, observed_at_unix=600)),
            self.adapter(claims=(SimpleNamespace(**dict(self.claim.__dict__, channel_uuid="wrong")),)),
        )
        for candidate in variants:
            with self.assertRaises(fixture.policy.VerifiedLivePolicyUnavailable):
                self.invoke(candidate)


if __name__ == "__main__":
    unittest.main()
