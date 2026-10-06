import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from atlas.sports_resource_pool import (
    SportsResourcePool, SportsResourcePoolExhausted,
    SportsResourcePoolStateError, SportsResourceUserLimitExceeded,
)

FP = 'a' * 64
CAP = {'account-1': 1}
BIND = {('game-1', 'account-1'): FP}

def concurrent_join(path, user, start, results):
    start.wait(10)
    pool = SportsResourcePool(Path(path), sharing_bindings=BIND)
    try:
        row = pool.acquire(user_id=user, target_id='game-1', candidate_source_ids=['account-1'], capacities=CAP, user_limit=1)
        results.put(row.lease_id)
    except Exception as error:
        results.put(type(error).__name__)

class SharedResourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'pool.json'
        self.now = 1000.0
        self.pool = SportsResourcePool(self.path, sharing_bindings=BIND, clock=lambda: self.now)

    def acquire(self, user, target='game-1', pool=None, capacities=None):
        return (pool or self.pool).acquire(user_id=user, target_id=target, candidate_source_ids=['account-1'], capacities=capacities or CAP, user_limit=1)

    def test_default_exclusive_state_and_behavior_preserved(self):
        pool = SportsResourcePool(self.path, clock=lambda: self.now)
        self.acquire('one', pool=pool)
        with self.assertRaises(SportsResourcePoolExhausted):
            self.acquire('two', pool=pool)
        self.assertEqual(json.loads(self.path.read_text())['version'], 1)

    def test_shared_consumers_use_one_allocation_and_last_release_frees_it(self):
        first = self.acquire('one'); second = self.acquire('two')
        self.assertNotEqual(first.lease_id, second.lease_id)
        self.assertEqual(self.pool.snapshot(capacities=CAP).active, 1)
        self.assertEqual(len(self.pool.snapshot(capacities=CAP).leases), 2)
        self.assertFalse(self.pool.release(lease_id=first.lease_id, user_id='two'))
        self.assertTrue(self.pool.release(lease_id=first.lease_id, user_id='one'))
        self.assertFalse(self.pool.release(lease_id=first.lease_id, user_id='one'))
        self.assertEqual(self.pool.snapshot(capacities=CAP).available, 0)
        self.pool.heartbeat(lease_id=second.lease_id, user_id='two')
        self.assertTrue(self.pool.release(lease_id=second.lease_id, user_id='two'))
        self.assertEqual(self.pool.snapshot(capacities=CAP).available, 1)
        self.assertEqual(json.loads(self.path.read_text())['version'], 2)

    def test_different_event_and_changed_binding_cannot_join(self):
        self.acquire('one')
        with self.assertRaises(SportsResourcePoolExhausted): self.acquire('two', target='game-2')
        changed = SportsResourcePool(self.path, clock=lambda: self.now, sharing_bindings={('game-1', 'account-1'): 'b' * 64})
        with self.assertRaises(SportsResourcePoolExhausted): self.acquire('two', pool=changed)

    def test_restart_preserves_binding_and_users_keep_limits(self):
        self.acquire('one')
        restarted = SportsResourcePool(self.path, clock=lambda: self.now, sharing_bindings=BIND)
        second = self.acquire('two', pool=restarted)
        self.assertEqual(second.sharing_fingerprint, FP)
        with self.assertRaises(SportsResourceUserLimitExceeded): self.acquire('one', pool=restarted)
        default = SportsResourcePool(self.path, clock=lambda: self.now)
        with self.assertRaises(SportsResourcePoolExhausted): self.acquire('three', pool=default)

    def test_legacy_lease_is_not_adopted_into_sharing(self):
        default = SportsResourcePool(self.path, clock=lambda: self.now)
        original = self.acquire('one', pool=default)
        with self.assertRaises(SportsResourcePoolExhausted): self.acquire('two')
        self.assertEqual(json.loads(self.path.read_text())['version'], 1)
        default.release(lease_id=original.lease_id, user_id='one')
        self.acquire('two'); self.acquire('three')

    def test_revoked_capacity_blocks_even_shared_join(self):
        self.acquire('one')
        with self.assertRaises(SportsResourcePoolExhausted):
            self.acquire('two', capacities={'account-1': 0})

    def test_independent_expiry_does_not_expire_live_consumer(self):
        self.acquire('one'); second = self.acquire('two')
        self.now += 60
        self.pool.heartbeat(lease_id=second.lease_id, user_id='two')
        self.now += 31
        snapshot = self.pool.snapshot(capacities=CAP)
        self.assertEqual({row.user_id for row in snapshot.leases}, {'one', 'two'})
        self.assertEqual(snapshot.active, 1)
        with self.assertRaises(SportsResourcePoolStateError): self.acquire('three')

    def test_invalid_fingerprint_state_fails_without_rewriting(self):
        self.acquire('one')
        data = json.loads(self.path.read_text())
        next(iter(data['leases'].values()))['sharing_fingerprint'] = 'bad'
        self.path.write_text(json.dumps(data))
        before = self.path.read_bytes()
        with self.assertRaises(SportsResourcePoolStateError): self.acquire('two')
        self.assertEqual(before, self.path.read_bytes())

    def test_invalid_server_binding_rejected_and_input_copied(self):
        for mapping in ({('game-1', 'account-1'): 'bad'}, {'game-1': FP}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                SportsResourcePool(self.path, sharing_bindings=mapping)
        bindings = dict(BIND)
        pool = SportsResourcePool(self.path, clock=lambda: self.now, sharing_bindings=bindings)
        bindings.clear()
        self.acquire('one', pool=pool); self.acquire('two', pool=pool)

    def test_concurrent_processes_keep_both_owners_in_one_slot(self):
        context = multiprocessing.get_context('fork')
        start = context.Event(); results = context.Queue()
        children = [context.Process(target=concurrent_join, args=(str(self.path), user, start, results)) for user in ('one', 'two')]
        try:
            for child in children: child.start()
            start.set()
            values = [results.get(timeout=15) for _ in children]
            for child in children:
                child.join(15)
                self.assertEqual(child.exitcode, 0)
            self.assertEqual(len(set(values)), 2)
            self.assertTrue(all(len(value) == 32 for value in values))
            pool = SportsResourcePool(self.path)
            snapshot = pool.snapshot(capacities=CAP)
            self.assertEqual(snapshot.active, 1)
            self.assertEqual(len(snapshot.leases), 2)
        finally:
            for child in children:
                if child.is_alive(): child.terminate(); child.join(5)
            results.close()

if __name__ == '__main__': unittest.main()
