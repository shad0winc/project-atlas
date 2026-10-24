"""Selection boundary tests; Redis atomicity has its own private probe."""

import importlib.util
import sys
import types
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ledger_path = ROOT / "apps/m3u/reservation_ledger.py"
ledger_spec = importlib.util.spec_from_file_location(
    "apps.m3u.reservation_ledger", ledger_path)
ledger = importlib.util.module_from_spec(ledger_spec)
for name in ("apps", "apps.m3u"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules[ledger_spec.name] = ledger
ledger_spec.loader.exec_module(ledger)

plan_path = ROOT / "apps/m3u/verified_live_plan.py"
plan_spec = importlib.util.spec_from_file_location(
    "apps.m3u.verified_live_plan", plan_path)
plan_module = importlib.util.module_from_spec(plan_spec)
sys.modules[plan_spec.name] = plan_module
plan_spec.loader.exec_module(plan_module)

selection_path = ROOT / "apps/proxy/live_proxy/verified_selection.py"
selection_spec = importlib.util.spec_from_file_location(
    "staged_verified_selection", selection_path)
selection = importlib.util.module_from_spec(selection_spec)
sys.modules[selection_spec.name] = selection
selection_spec.loader.exec_module(selection)


class Query:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self

    def order_by(self, *_args):
        return self.rows

    def filter(self, **_kwargs):
        return self.rows


def fixture(*, second=False):
    channel_id = uuid.uuid4()
    owner_lease = "worker|lease-unique"
    profile = SimpleNamespace(id=21, is_default=True)
    account = SimpleNamespace(id=31, is_active=True,
        profiles=Query([profile]), get_user_agent_string=lambda: "test-agent")
    streams = [SimpleNamespace(id=11, m3u_account=account)]
    if second:
        account_2 = SimpleNamespace(id=32, is_active=True,
            profiles=Query([SimpleNamespace(id=22, is_default=True)]),
            get_user_agent_string=lambda: "test-agent")
        streams.append(SimpleNamespace(id=12, m3u_account=account_2))
    output = SimpleNamespace(id=41, is_proxy=lambda: True,
                             is_redirect=lambda: False)
    channel = SimpleNamespace(uuid=channel_id, streams=Query(streams),
                              get_stream_profile=lambda: output)

    def policy(ch, stream, prof, acct, lease):
        spec = ledger.ReservationSpec(
            mode="live", owner_id=f"{ch.uuid}|{lease}",
            stream_id=stream.id, profile_id=prof.id, account_id=acct.id,
            credential_scope="a" * 64, profile_capacity=1,
            account_capacity=1, credential_capacity=1)
        return plan_module.VerifiedLivePlan(
            spec=spec, upstream_url="http://internal.invalid/secret")

    return channel, owner_lease, policy


class SelectionTests(unittest.TestCase):
    def test_selected_handle_keeps_one_token_and_does_not_print_url(self):
        channel, lease, policy = fixture()
        with patch.object(selection, "reserve_live_channel",
                          return_value=("b" * 32, 1)) as reserve:
            result = selection.select_verified_channel(object(), channel=channel,
                owner_lease=lease, policy=policy)
        self.assertEqual(result.stream_id, 11)
        self.assertEqual(result.profile_id, 21)
        self.assertEqual(result.account_id, 31)
        self.assertEqual(result.token, "b" * 32)
        self.assertNotIn("secret", repr(result))
        self.assertEqual(reserve.call_count, 1)

    def test_setup_failure_releases_only_pending_token(self):
        channel, lease, policy = fixture()
        channel.streams.rows[0].m3u_account.get_user_agent_string = (
            lambda: (_ for _ in ()).throw(RuntimeError("sensitive transport details")))
        with patch.object(selection, "reserve_live_channel",
                          return_value=("b" * 32, 1)), patch.object(
                          selection, "release_pending_live_channel",
                          return_value=True) as release:
            with self.assertRaises(selection.VerifiedSelectionError) as caught:
                selection.select_verified_channel(object(), channel=channel,
                    owner_lease=lease, policy=policy)
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertEqual(release.call_count, 1)
        self.assertEqual(release.call_args.args[2], "b" * 32)

    def test_full_candidate_tries_next_without_duplicate_reservation(self):
        channel, lease, policy = fixture(second=True)
        with patch.object(selection, "reserve_live_channel",
                          side_effect=[ledger.ReservationFull("full"),
                                       ("c" * 32, 1)]) as reserve:
            result = selection.select_verified_channel(object(), channel=channel,
                owner_lease=lease, policy=policy)
        self.assertEqual(result.stream_id, 12)
        self.assertEqual(reserve.call_count, 2)

    def test_untrusted_identity_is_rejected_before_redis_allocation(self):
        channel, lease, policy = fixture()
        def wrong_policy(*args):
            spec = ledger.ReservationSpec(
                mode="live", owner_id=f"{channel.uuid}|{lease}",
                stream_id=11, profile_id=21, account_id=99,
                credential_scope="a" * 64, profile_capacity=1,
                account_capacity=1, credential_capacity=1)
            return plan_module.VerifiedLivePlan(spec, "http://internal.invalid/secret")
        with patch.object(selection, "reserve_live_channel") as reserve:
            with self.assertRaises(selection.VerifiedSelectionError):
                selection.select_verified_channel(object(), channel=channel,
                    owner_lease=lease, policy=wrong_policy)
        reserve.assert_not_called()

    def test_redirect_profile_cannot_bypass_shared_proxy_reservation(self):
        channel, lease, policy = fixture()
        channel.get_stream_profile = lambda: SimpleNamespace(
            id=41, is_proxy=lambda: False, is_redirect=lambda: True)
        with patch.object(selection, "reserve_live_channel") as reserve:
            with self.assertRaises(selection.VerifiedSelectionError):
                selection.select_verified_channel(object(), channel=channel,
                    owner_lease=lease, policy=policy)
        reserve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
