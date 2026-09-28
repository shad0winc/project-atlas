"""Bounded per-viewer source checks while Redis attestation stays per batch."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for package in ("apps", "apps.m3u"):
    module = types.ModuleType(package)
    module.__path__ = []
    sys.modules.setdefault(package, module)

ledger_path = ROOT / "apps/m3u/reservation_ledger.py"
ledger_spec = importlib.util.spec_from_file_location(
    "apps.m3u.reservation_ledger", ledger_path)
ledger = importlib.util.module_from_spec(ledger_spec)
sys.modules[ledger_spec.name] = ledger
ledger_spec.loader.exec_module(ledger)
cache_path = ROOT / "apps/proxy/live_proxy/verified_policy_cache.py"
cache_spec = importlib.util.spec_from_file_location("staged_policy_cache", cache_path)
cache_module = importlib.util.module_from_spec(cache_spec)
sys.modules[cache_spec.name] = cache_module
cache_spec.loader.exec_module(cache_module)


class CacheTests(unittest.TestCase):
    def test_short_reuse_identity_change_and_expired_failure(self):
        seconds = [100.0]
        calls = []
        fail = [False]

        def builder(stream_id, profile_id, account_id, owner_lease):
            calls.append((stream_id, profile_id, account_id, owner_lease))
            if fail[0]:
                raise RuntimeError("policy unavailable")
            return ledger.ReservationSpec(
                mode="live", owner_id=f"channel|{owner_lease}",
                stream_id=stream_id, profile_id=profile_id,
                account_id=account_id, credential_scope="a" * 64,
                profile_capacity=1, account_capacity=1,
                credential_capacity=1)

        cache = cache_module.VerifiedPolicyCache(
            builder, ttl_seconds=20, clock=lambda: seconds[0])
        first = cache.build(11, 21, 31, "lease-1")
        seconds[0] = 119.9
        self.assertIs(cache.build(11, 21, 31, "lease-1"), first)
        self.assertEqual(len(calls), 1)
        changed = cache.build(12, 21, 31, "lease-1")
        self.assertEqual(changed.stream_id, 12)
        self.assertEqual(len(calls), 2)
        seconds[0] = 140.0
        fail[0] = True
        with self.assertRaises(RuntimeError):
            cache.build(12, 21, 31, "lease-1")
        self.assertEqual(len(calls), 3)
        seconds[0] = 140.1
        with self.assertRaises(RuntimeError):
            cache.build(12, 21, 31, "lease-1")
        self.assertEqual(len(calls), 4)
        self.assertNotIn("a" * 64, repr(cache))

    def test_clock_regression_refetches_and_invalid_results_are_rejected(self):
        seconds = [10.0]
        calls = [0]
        def builder(*_):
            calls[0] += 1
            return ledger.ReservationSpec(
                mode="live", owner_id="channel|lease", stream_id=1,
                profile_id=1, account_id=1, credential_scope="a" * 64,
                profile_capacity=1, account_capacity=1,
                credential_capacity=1)
        cache = cache_module.VerifiedPolicyCache(builder, clock=lambda: seconds[0])
        cache.build(1, 1, 1, "lease")
        seconds[0] = 9.0
        cache.build(1, 1, 1, "lease")
        self.assertEqual(calls[0], 2)
        bad = cache_module.VerifiedPolicyCache(lambda *_: object())
        with self.assertRaises(ValueError):
            bad.build(1, 1, 1, "lease")


if __name__ == "__main__":
    unittest.main()
