"""Direct modified-state recovery, real process death and cooperative fencing."""
import contextlib
import importlib.util
import io
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('consumer_recovery_drill',ROOT/'scripts/diagnostics/sports-recovery-consumption-drill.py')
drill=importlib.util.module_from_spec(spec);spec.loader.exec_module(drill)
c=drill.consumption;pub=c.publication


def held_writer(root,ready,release):
    with c.writer(root):ready.set();release.wait(10)


def dying_writer(root):
    # mutate obtains and releases a lease; this second lease proves process
    # death releases an active fence without pretending it is a service stop.
    drill.mutate(root)
    with c.writer(root):os._exit(86)


class ConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.',dir='/tmp')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.original=drill.fixture(self.root)

    def armed(self):c.arm(self.root)
    def modified(self):self.armed();drill.mutate(self.root)
    def verify(self):drill.verify(self.root,self.original)

    def test_direct_consumer_writes_recover_old_and_quarantine_changed_bytes(self):
        self.modified();c.recover(self.root);c.recover(self.root);self.verify()
        sealed=pub.read_json(self.root/'consumption/SEAL.json')['surfaces']
        self.assertTrue(all(row['new_sha256']!=new['consumed_sha256'] for row,new in zip(self.original,sealed)))
        with self.assertRaises(c.ConsumptionError):
            with c.writer(self.root):pass

    def test_all_real_process_death_boundaries_resume_and_repeat_safely(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):self.assertEqual(drill.run_cases(),16)
        self.assertEqual(output.getvalue().count('=PASS boundary='),16)

    def test_live_cooperative_writer_blocks_seal_and_recovery_without_status_change(self):
        self.armed();ctx=multiprocessing.get_context('fork');ready=ctx.Event();release=ctx.Event()
        process=ctx.Process(target=held_writer,args=(self.root,ready,release));process.start()
        try:
            self.assertTrue(ready.wait(5))
            for operation in (c.seal,c.recover):
                with self.assertRaises(BlockingIOError):operation(self.root)
            self.assertEqual(pub.read_json(self.root/'consumption/STATUS.json'),{'state':'open'})
        finally:
            release.set();process.join(5)
            if process.is_alive():process.kill();process.join(2)
        self.assertEqual(process.exitcode,0);c.recover(self.root);self.verify()

    def test_killed_writer_releases_fence_and_changed_state_is_retained(self):
        self.armed();process=multiprocessing.get_context('fork').Process(target=dying_writer,args=(self.root,))
        process.start();process.join(5)
        if process.is_alive():process.kill();process.join(2)
        self.assertEqual(process.exitcode,86);c.recover(self.root);self.verify()

    def test_missing_final_seal_cannot_be_regenerated_after_sealed_status(self):
        self.modified();c.seal(self.root)
        (self.root/'consumption/SEAL.json').unlink()
        with self.assertRaises(c.ConsumptionError):c.recover(self.root)
        self.assertTrue(all((self.root/'transaction/old'/n).exists() for n in pub.SURFACES))
        self.assertFalse(any((self.root/'consumption/quarantine').iterdir()))

    def test_published_seal_is_never_rebound_to_off_protocol_changes(self):
        self.modified()
        def stop(name):
            if name=='seal-written':raise RuntimeError('interrupted')
        with patch.object(c,'checkpoint',side_effect=stop),self.assertRaises(RuntimeError):c.seal(self.root)
        before=(self.root/'consumption/SEAL.json').read_bytes()
        (self.root/'current/dispatcharr-jwt').write_bytes(b'off-protocol-change')
        with self.assertRaises(c.ConsumptionError):c.recover(self.root)
        self.assertEqual((self.root/'consumption/SEAL.json').read_bytes(),before)
        self.assertFalse(any((self.root/'consumption/quarantine').iterdir()))

    def test_old_state_tamper_blocks_all_moves(self):
        self.modified();(self.root/'transaction/old/dispatcharr-jwt').write_bytes(b'tampered')
        with self.assertRaises(c.ConsumptionError):c.recover(self.root)
        self.assertFalse(any((self.root/'consumption/quarantine').iterdir()))
        self.assertTrue(all((self.root/'current'/n).exists() for n in pub.SURFACES))

    def test_invalid_current_modes_links_or_extra_adjacent_journals_are_held(self):
        self.modified();path=self.root/'current/dispatcharr-jwt';raw=path.read_bytes()
        path.chmod(0o644)
        with self.assertRaises(pub.PublicationError):c.recover(self.root)
        path.chmod(0o600);path.unlink();path.symlink_to(self.root/'transaction/old/dispatcharr-jwt')
        with self.assertRaises(pub.PublicationError):c.recover(self.root)
        path.unlink();drill.write(path,raw)
        drill.write(self.root/'current/teamarr-db-wal',b'unsupported-adjacent-wal')
        with self.assertRaises(c.ConsumptionError):c.recover(self.root)
        self.assertFalse(any((self.root/'consumption/quarantine').iterdir()))

    def test_tampered_quarantine_blocks_repeat_recovery_before_any_other_move(self):
        self.modified()
        def stop(name):
            if name=='quarantine:sports-metadata-policy':raise RuntimeError('interrupted')
        with patch.object(c,'checkpoint',side_effect=stop),self.assertRaises(RuntimeError):c.recover(self.root)
        path=self.root/'consumption/quarantine/sports-metadata-policy/refresh.json';path.write_bytes(b'tampered')
        with patch.object(pub,'move') as move,self.assertRaises(c.ConsumptionError):c.recover(self.root)
        move.assert_not_called()

    def test_after_rename_fsync_failure_is_resumable(self):
        self.modified();real=pub.sync;calls=[0]
        def fail_once(path):
            if path==self.root/'current' and calls[0]==0:
                calls[0]+=1;raise OSError('fsync failure')
            return real(path)
        with patch.object(pub,'sync',side_effect=fail_once),self.assertRaises(OSError):c.recover(self.root)
        c.recover(self.root);self.verify()

    def test_sealing_fences_future_writers_even_before_seal_document_exists(self):
        self.modified()
        def stop(name):
            if name=='sealing':raise RuntimeError('interrupted')
        with patch.object(c,'checkpoint',side_effect=stop),self.assertRaises(RuntimeError):c.seal(self.root)
        self.assertFalse((self.root/'consumption/SEAL.json').exists())
        with self.assertRaises(c.ConsumptionError):
            with c.writer(self.root):pass
        c.recover(self.root);self.verify()

    def test_plan_or_exposure_changes_are_not_accepted(self):
        self.armed();path=self.root/'transaction/PLAN.json';raw=path.read_bytes()
        path.write_bytes(raw+b' ')
        with self.assertRaises(c.ConsumptionError):c.recover(self.root)
        path.write_bytes(raw)
        exposure=self.root/'consumption/EXPOSURE.json'
        value=pub.read_json(exposure);value['ready_for_live_apply']=True;pub.write_json(exposure,value)
        with self.assertRaises(c.ConsumptionError):c.recover(self.root)

    def test_arm_requires_complete_applied_state_and_refuses_retry(self):
        pub.write_json(self.root/'transaction/STATUS.json',{'state':'staged'})
        with self.assertRaises(c.ConsumptionError):c.arm(self.root)
        self.assertFalse((self.root/'consumption').exists())
        pub.write_json(self.root/'transaction/STATUS.json',{'state':'applied-awaiting-verification'})
        self.armed()
        with self.assertRaises(pub.PublicationError):c.arm(self.root)

    def test_partial_arm_blocks_legacy_recovery_and_all_new_writers(self):
        with patch.object(pub,'write_json',side_effect=OSError('disk failure')),self.assertRaises(OSError):c.arm(self.root)
        with self.assertRaises(pub.PublicationError):pub.recover(self.root)
        with self.assertRaises((OSError,ValueError)):
            with c.writer(self.root):pass
        self.assertTrue(all((self.root/'transaction/old'/n).exists() for n in pub.SURFACES))

    def test_lock_symlinks_and_nonprivate_roots_are_rejected(self):
        (self.root/'consumer.lock').symlink_to(self.root/'transaction/PLAN.json')
        with self.assertRaises(OSError):c.arm(self.root)
        (self.root/'consumer.lock').unlink();self.root.chmod(0o755)
        with self.assertRaises(pub.PublicationError):c.arm(self.root)
        self.root.chmod(0o700)

    def test_generic_api_remains_blocked_after_new_recovery(self):
        self.modified();c.recover(self.root)
        for operation in (pub.apply,pub.recover):
            with self.assertRaises(pub.PublicationError):operation(self.root)
        self.verify()


if __name__=='__main__':unittest.main()
