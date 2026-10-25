"""Read-only cross-worker lookup contract; real Redis validates Lua separately."""

import importlib.util
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


path = Path(__file__).resolve().parents[1] / "apps/m3u/reservation_ledger.py"
module_spec = importlib.util.spec_from_file_location("resume_ledger", path)
ledger = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = ledger
module_spec.loader.exec_module(ledger)


class Redis:
    def __init__(self, channel):
        self.channel = channel
        self.alias = {
            b"token": b"a" * 32, b"owner_lease": b"worker|lease",
            b"stream_id": b"11", b"profile_id": b"21",
            b"account_id": b"31",
        }
        self.grant = {b"worker": b"worker|lease", b"epoch": b"4"}
        self.generation = b"4-fresh"

    def hgetall(self, key):
        if key.endswith(":grant"):
            return self.grant
        if key.endswith(f"live:channel:{self.channel}"):
            return self.alias
        raise AssertionError("Unexpected Redis key")

    def get(self, key):
        assert key.endswith(f"{self.channel}:generation")
        return self.generation


class ResumeTests(unittest.TestCase):
    def test_trusted_policy_rebuilt_and_lua_join_receives_advisory_identity(self):
        channel = str(uuid.uuid4())
        redis = Redis(channel)
        def policy(stream, profile, account, lease):
            return ledger.ReservationSpec(
                mode="live", owner_id=f"{channel}|{lease}",
                stream_id=stream, profile_id=profile, account_id=account,
                credential_scope="f" * 64, profile_capacity=1,
                account_capacity=1, credential_capacity=1)
        with patch.object(ledger, "attest_live_join",
                          return_value=(11, 21, 31)) as attest:
            result = ledger.attest_current_live_channel(redis,
                channel_id=channel, chunk_index=7, spec_builder=policy)
        self.assertEqual(result, (11, 21, 31))
        self.assertEqual(attest.call_args.kwargs["worker_id"], "worker|lease")
        self.assertEqual(attest.call_args.kwargs["grant_epoch"], 4)
        self.assertEqual(attest.call_args.kwargs["generation_id"], "4-fresh")
        self.assertEqual(attest.call_args.kwargs["chunk_index"], 7)

    def test_replaced_worker_and_wrong_policy_do_not_attest(self):
        channel = str(uuid.uuid4())
        redis = Redis(channel)
        redis.grant[b"worker"] = b"replacement"
        with patch.object(ledger, "attest_live_join") as attest:
            self.assertIsNone(ledger.attest_current_live_channel(redis,
                channel_id=channel, chunk_index=7,
                spec_builder=lambda *_: None))
        attest.assert_not_called()
        redis.grant[b"worker"] = b"worker|lease"
        with patch.object(ledger, "attest_live_join") as attest:
            with self.assertRaises(ledger.ReservationError):
                ledger.attest_current_live_channel(redis, channel_id=channel,
                    chunk_index=7, spec_builder=lambda *_: None)
        attest.assert_not_called()

    def test_reader_generation_must_match_join_generation(self):
        channel = str(uuid.uuid4())
        redis = Redis(channel)
        with patch.object(ledger, "attest_live_join") as attest:
            result = ledger.attest_current_live_channel(
                redis, channel_id=channel, chunk_index=7,
                spec_builder=lambda *_: None,
                expected_grant_epoch=5,
                expected_generation_id="4-fresh",
            )
        self.assertIsNone(result)
        attest.assert_not_called()


if __name__ == "__main__":
    unittest.main()
