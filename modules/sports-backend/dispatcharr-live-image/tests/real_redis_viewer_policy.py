"""Private Redis gate for live viewer policy identity and capacity."""

import importlib.util
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import replace
from pathlib import Path

import redis


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ledger = load("viewer_ledger_probe", ROOT / "apps/m3u/reservation_ledger.py")
authority_module = load("viewer_authority_probe",
                        ROOT / "apps/proxy/live_proxy/generation_authority.py")


def check(client):
    client.set(ledger.CUTOVER_KEY, "ledger")
    channel = str(uuid.uuid4())
    owner = "worker|" + uuid.uuid4().hex
    owner_key = f"live:channel:{channel}:owner"
    client.set(owner_key, owner, ex=90)
    authority = authority_module.GenerationAuthority(client, lease_seconds=90)
    grant = authority.acquire(channel_id=channel, worker_id=owner,
                              owner_key=owner_key)
    generation = f"{grant.epoch}-{uuid.uuid4().hex}"
    authority.activate_generation(channel_id=channel, grant_token=grant.token,
                                  generation_id=generation)
    spec = ledger.ReservationSpec(
        mode="live", owner_id=f"{channel}|{owner}", stream_id=11,
        profile_id=21, account_id=31, credential_scope="a" * 64,
        profile_capacity=2, account_capacity=2, credential_capacity=2)
    token, _ = ledger.reserve_live_channel(client, spec, channel_id=channel,
                                           owner_lease=owner)
    index = authority.publish_buffer_chunk(
        channel_id=channel, grant_token=grant.token,
        generation_id=generation,
        buffer_index_key=f"live:channel:{channel}:input:buffer:index",
        buffer_chunk_prefix=f"live:channel:{channel}:input:buffer:chunk:",
        chunk=b"\x47" + b"A" * 187, chunk_ttl=90, owner_key=owner_key)
    args = dict(channel_id=channel, worker_id=owner, grant_epoch=grant.epoch,
                generation_id=generation, chunk_index=index)
    assert ledger.activate_verified_live(client, spec, token,
        grant_token=grant.token, **args)
    assert ledger.attest_live_join(client, spec, token, **args) == (11, 21, 31)

    wrong_realm = replace(spec, credential_scope="b" * 64)
    try:
        ledger.attest_live_join(client, wrong_realm, token, **args)
    except ledger.ReservationError:
        pass
    else:
        raise AssertionError("A new credential realm reused old admission")
    print("changed_credential_realm_refuses_join=PASS")

    second = str(uuid.uuid4())
    second_owner = "worker|" + uuid.uuid4().hex
    client.set(f"live:channel:{second}:owner", second_owner, ex=90)
    second_spec = replace(spec, owner_id=f"{second}|{second_owner}")
    second_token, _ = ledger.reserve_live_channel(client, second_spec,
        channel_id=second, owner_lease=second_owner)
    lowered = replace(spec, profile_capacity=1, account_capacity=1,
                      credential_capacity=1)
    try:
        ledger.attest_live_join(client, lowered, token, **args)
    except ledger.ReservationError:
        pass
    else:
        raise AssertionError("A lowered provider capacity admitted an overfull pool")
    assert ledger.release_pending_live_channel(client, second_spec,
        second_token, channel_id=second, owner_lease=second_owner)
    assert ledger.attest_live_join(client, lowered, token, **args) == (11, 21, 31)
    print("fresh_capacity_bound_refuses_overfull_join=PASS")

    def policy(stream_id, profile_id, account_id, lease):
        assert (stream_id, profile_id, account_id, lease) == (11, 21, 31, owner)
        return wrong_realm

    try:
        ledger.attest_current_live_channel(client, channel_id=channel,
            chunk_index=index, spec_builder=policy,
            expected_grant_epoch=grant.epoch,
            expected_generation_id=generation)
    except ledger.ReservationError:
        pass
    else:
        raise AssertionError("A cross-worker policy mismatch reused the live alias")
    assert ledger.attest_current_live_channel(client, channel_id=channel,
        chunk_index=index, spec_builder=lambda *_: lowered,
        expected_grant_epoch=grant.epoch,
        expected_generation_id=generation) == (11, 21, 31)
    print("cross_worker_policy_scope_recheck=PASS")


def main():
    with tempfile.TemporaryDirectory(prefix="atlas-viewer-policy-") as directory:
        socket = str(Path(directory) / "redis.sock")
        process = subprocess.Popen([
            "redis-server", "--port", "0", "--unixsocket", socket,
            "--unixsocketperm", "700", "--save", "", "--appendonly", "no",
            "--dir", directory,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            client = redis.Redis(unix_socket_path=socket)
            for _ in range(100):
                try:
                    if client.ping():
                        break
                except redis.RedisError:
                    time.sleep(0.05)
            else:
                raise RuntimeError("Disposable Redis did not start")
            check(client)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
