"""Trusted policy assembly; live Redis admission is covered separately."""

import importlib.util
import sys
import types
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
for name in ("apps", "apps.m3u"):
    sys.modules.setdefault(name, types.ModuleType(name))
if "apps.m3u.reservation_ledger" not in sys.modules:
    path = ROOT / "apps/m3u/reservation_ledger.py"
    spec = importlib.util.spec_from_file_location("apps.m3u.reservation_ledger", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

path = ROOT / "apps/m3u/verified_live_policy.py"
spec = importlib.util.spec_from_file_location("staged_verified_live_policy", path)
policy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = policy
spec.loader.exec_module(policy)


def inputs(*, account_id=31, realm="provider-realm-a", username="play-user",
           password="sensitive-play-password"):
    channel_id = str(uuid.uuid4())
    return dict(
        channel_id=channel_id, owner_lease="worker-lease-1",
        stream=SimpleNamespace(id=11, m3u_account_id=account_id),
        profile=SimpleNamespace(id=21, m3u_account_id=account_id, max_streams=3),
        account=SimpleNamespace(id=account_id, account_type="XC", is_active=True,
                                max_streams=2),
        binding=policy.TrustedSourceBinding("source-1", channel_id, account_id, 21,
                                            realm, 4, True),
        event_resource_source_ids=frozenset({"source-1"}),
        observation=policy.TrustedCapacityObservation(account_id, realm,
                                                       "active", 1, 1000),
        transformed_username=username, transformed_password=password,
        scope_key=b"secret-server-key-only-for-this-test-00001", now_unix=1001,
    )


class VerifiedLivePolicyTests(unittest.TestCase):
    def test_bounds_and_opaque_scope(self):
        data = inputs()
        result = policy.build_verified_live_spec(**data)
        self.assertEqual((result.profile_capacity, result.account_capacity,
                          result.credential_capacity), (1, 1, 1))
        self.assertEqual((result.stream_id, result.profile_id, result.account_id),
                         (11, 21, 31))
        self.assertEqual(result.owner_id, data["channel_id"] + "|worker-lease-1")
        self.assertEqual(len(result.credential_scope), 64)
        self.assertNotIn(data["transformed_password"], repr(result))
        self.assertNotIn(data["transformed_password"], repr(data["binding"]))

    def test_scope_shared_for_same_effective_login_across_accounts(self):
        a = policy.build_verified_live_spec(**inputs())
        b = policy.build_verified_live_spec(**inputs(account_id=32))
        self.assertEqual(a.credential_scope, b.credential_scope)
        self.assertNotEqual(a.account_key, b.account_key)
        self.assertEqual(a.credential_key, b.credential_key)

    def test_realm_transformation_and_key_separate_scope(self):
        base = policy.build_verified_live_spec(**inputs()).credential_scope
        variants = (inputs(realm="provider-realm-b"),
                    inputs(username="transformed-user"),
                    inputs(password="another-secret"),
                    dict(inputs(), scope_key=b"another-secret-server-key-000000001"))
        for variant in variants:
            with self.subTest(variant=variant["binding"].canonical_realm):
                self.assertNotEqual(base, policy.build_verified_live_spec(
                    **variant).credential_scope)

    def test_stale_mismatch_and_unbounded_evidence_fail_closed(self):
        cases = [
            dict(inputs(), now_unix=1301),
            dict(inputs(), now_unix=999),
            dict(inputs(), observation=replace(inputs()["observation"], account_id=32)),
            dict(inputs(), observation=replace(inputs()["observation"],
                                               canonical_realm="provider-realm-b")),
            dict(inputs(), observation=replace(inputs()["observation"],
                                               provider_max_connections=0)),
            dict(inputs(), binding=replace(inputs()["binding"], enabled=False)),
            dict(inputs(), binding=replace(inputs()["binding"], profile_id=22)),
            dict(inputs(), binding=replace(inputs()["binding"],
                                           channel_id=str(uuid.uuid4()))),
            dict(inputs(), event_resource_source_ids=frozenset({"unrelated-source"})),
            dict(inputs(), event_resource_source_ids=frozenset()),
            dict(inputs(), account=SimpleNamespace(id=31, account_type="XC",
                          is_active=True, max_streams=0)),
            dict(inputs(), scope_key=b"short"),
            dict(inputs(), channel_id="invalid-channel-id"),
        ]
        for case in cases:
            with self.subTest(case=str(len(case)) + repr(case["observation"].status)):
                with self.assertRaises(policy.VerifiedLivePolicyUnavailable) as caught:
                    policy.build_verified_live_spec(**case)
                self.assertNotIn("sensitive-play-password", str(caught.exception))

    def test_min_of_local_and_observed_limits(self):
        data = inputs()
        data["observation"] = replace(data["observation"], provider_max_connections=5)
        result = policy.build_verified_live_spec(**data)
        self.assertEqual((result.profile_capacity, result.account_capacity,
                          result.credential_capacity), (3, 2, 4))


if __name__ == "__main__":
    unittest.main()
