import tempfile
import unittest
from pathlib import Path
from atlas.sports_resource_pool import SportsResourcePool, SportsResourcePoolExhausted, SportsResourcePoolStateError

class CleanupReservations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'pool.json'
        self.now = 1000
        self.bindings = {('game', 'account'): 'a' * 64}
        self.pool = self.make_pool()
    def make_pool(self, enabled=True):
        return SportsResourcePool(self.path, clock=lambda: self.now, sharing_bindings=self.bindings if enabled else None)
    def acquire(self, user, target='game', pool=None):
        return (pool or self.pool).acquire(user_id=user, target_id=target, candidate_source_ids=['account'], capacities={'account': 1})
    def test_timeout_does_not_free_physical_allocation_after_restart_or_disable(self):
        lease = self.acquire('one')
        self.now += 91
        for pool in (self.make_pool(), self.make_pool(False)):
            with self.assertRaises(SportsResourcePoolExhausted):
                self.acquire('two', target='other', pool=pool)
            self.assertEqual(pool.snapshot(capacities={'account': 1}).active, 1)
        self.assertTrue(self.pool.release(lease_id=lease.lease_id, user_id='one'))
        self.acquire('two', target='other')
    def test_expired_consumer_blocks_join_without_rewriting_evidence(self):
        first = self.acquire('one'); second = self.acquire('two')
        self.now += 60
        self.pool.heartbeat(lease_id=second.lease_id, user_id='two')
        self.now += 31
        before = self.path.read_bytes()
        with self.assertRaises(SportsResourcePoolStateError): self.acquire('three')
        with self.assertRaises(SportsResourcePoolStateError):
            self.pool.heartbeat(lease_id=first.lease_id, user_id='one')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.pool.release(lease_id=first.lease_id, user_id='two'))
        self.assertTrue(self.pool.release(lease_id=first.lease_id, user_id='one'))
        self.acquire('three')
    def test_legacy_timeout_behavior_is_preserved(self):
        pool = self.make_pool(False)
        self.acquire('one', pool=pool)
        self.now += 91
        self.acquire('two', target='other', pool=pool)

if __name__ == '__main__': unittest.main()
