"""Native durable file ordering, refusal and actual abrupt-process boundaries."""
import fcntl
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[2] / 'scripts/lib/deployment-durable-io.py'
spec = importlib.util.spec_from_file_location('atlas_deployment_durable_io_test', HELPER)
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)


class DurablePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.current = self.root / 'current'
        self.current.write_text('baseline-original\n');self.current.chmod(0o640)
        self.owner = self.root / 'owner';self.owner.write_bytes(b'deployment_id=original-failed\npid=123\n')
        self.flag = self.root / 'enabled';self.flag.touch()
        self.protected = self.owner.read_bytes(), self.owner.stat(), self.flag.stat()

    def tearDown(self):
        self.assertEqual(self.owner.read_bytes(), self.protected[0])
        self.assertEqual(self.owner.stat(), self.protected[1])
        self.assertEqual(self.flag.stat(), self.protected[2])
        self.temporary.cleanup()

    def test_atomic_write_flushes_file_then_replaces_then_flushes_parent(self):
        events=[];original_sync=os.fsync;original_replace=os.replace
        def sync(fd):
            events.append('directory-sync' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file-sync')
            return original_sync(fd)
        def replace(source,target):
            self.assertEqual(events,['file-sync']);events.append('replace');return original_replace(source,target)
        with patch.object(io.os,'fsync',sync),patch.object(io.os,'replace',replace):
            io.atomic_token(self.current,'baseline-new')
        self.assertEqual(events,['file-sync','replace','directory-sync'])
        self.assertEqual(self.current.read_bytes(),b'baseline-new\n')
        self.assertEqual(stat.S_IMODE(self.current.stat().st_mode),0o640)

    def test_before_replace_fsync_failure_preserves_previous_pointer(self):
        with patch.object(io.os,'fsync',side_effect=OSError('injected')):
            with self.assertRaises(OSError):io.atomic_token(self.current,'baseline-new')
        self.assertEqual(self.current.read_bytes(),b'baseline-original\n')
        self.assertEqual(list(self.root.glob('.current.durable-*')),[])

    def test_after_replace_directory_failure_is_reported_and_retry_is_safe(self):
        original=os.fsync
        def sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError('injected')
            return original(fd)
        with patch.object(io.os,'fsync',sync):
            with self.assertRaises(OSError):io.atomic_token(self.current,'baseline-new')
        self.assertEqual(self.current.read_bytes(),b'baseline-new\n')
        io.atomic_token(self.current,'baseline-new')

    def test_concurrent_target_change_is_refused(self):
        def checkpoint(phase):
            if phase=='file_fsynced':self.current.write_text('other-operation\n')
        with self.assertRaises(io.DurabilityError):io.atomic_token(self.current,'baseline-new',checkpoint=checkpoint)
        self.assertEqual(self.current.read_text(),'other-operation\n')

    def test_target_symlink_and_hardlink_are_refused(self):
        for kind in ('symlink','hardlink'):
            self.current.unlink(missing_ok=True)
            if kind=='symlink':self.current.symlink_to(self.owner)
            else:
                other=self.root/'other';other.write_text('fixture\n');os.link(other,self.current)
            with self.assertRaises(io.DurabilityError):io.atomic_token(self.current,'baseline-new')
            self.current.unlink()

    def test_invalid_target_name_and_token_are_refused(self):
        for path,value in ((self.owner,'new'),(self.current,'../bad'),(self.current,'bad\nvalue'),(self.current,'')):
            with self.assertRaises(io.DurabilityError):io.atomic_token(path,value)
        self.assertEqual(self.current.read_text(),'baseline-original\n')

    def test_missing_target_is_created_with_regular_mode(self):
        path=self.root/'status';io.atomic_token(path,'verified')
        self.assertEqual(path.read_bytes(),b'verified\n')
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o644)

    def test_group_writable_directory_is_refused(self):
        self.root.chmod(0o770)
        with self.assertRaises(io.DurabilityError):io.atomic_token(self.current,'new')
        self.root.chmod(0o700)

    def test_generation_flushes_files_before_containing_namespace(self):
        tree=self.root/'generation';(tree/'nested').mkdir(parents=True)
        (tree/'nested/code.py').write_text('pass\n')
        environment=self.root/'.env';environment.write_text('fixture=1\n')
        (tree/'.env').symlink_to(environment)
        events=[];original=os.fsync
        def sync(fd):
            events.append('d' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'f');return original(fd)
        with patch.object(io.os,'fsync',sync):io.sync_generation(tree,environment)
        self.assertEqual(events,['f','d','d','d'])
        self.assertEqual(environment.read_text(),'fixture=1\n')

    def test_generation_rejects_other_symlink_and_hardlinked_file(self):
        tree=self.root/'generation';tree.mkdir()
        link=tree/'unexpected';link.symlink_to(self.owner)
        with self.assertRaises(io.DurabilityError):io.sync_generation(tree,self.root/'.env')
        link.unlink();other=self.root/'other';other.write_text('fixture\n');os.link(other,link)
        with self.assertRaises(io.DurabilityError):io.sync_generation(tree,self.root/'.env')
        link.unlink()

    def test_generation_environment_link_must_match_the_native_overlay(self):
        tree=self.root/'generation';tree.mkdir();(tree/'.env').symlink_to(self.owner)
        with self.assertRaises(io.DurabilityError):io.sync_generation(tree,self.root/'.env')

    def test_generation_file_flush_failure_aborts(self):
        tree=self.root/'generation';tree.mkdir();(tree/'code.py').write_text('pass\n')
        with patch.object(io.os,'fsync',side_effect=OSError('injected')):
            with self.assertRaises(OSError):io.sync_generation(tree,self.root/'.env')

    def test_process_death_at_each_durability_checkpoint_keeps_recovery_held(self):
        code='''import importlib.util,os,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('durable',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def checkpoint(phase):
 if phase==sys.argv[3]:os._exit(73)
m.atomic_token(Path(sys.argv[2]),'baseline-new',checkpoint=checkpoint)
'''
        for phase in ('file_fsynced','replaced','directory_fsynced'):
            with self.subTest(phase=phase):
                self.current.write_text('baseline-original\n')
                result=subprocess.run([sys.executable,'-B','-c',code,str(HELPER),str(self.current),phase],capture_output=True)
                self.assertEqual(result.returncode,73,result.stderr)
                self.assertEqual(self.current.read_text(),'baseline-original\n' if phase=='file_fsynced' else 'baseline-new\n')
                self.assertTrue(self.flag.is_file());self.assertEqual(self.owner.read_bytes(),self.protected[0])
                io.atomic_token(self.current,'baseline-new')


if __name__=='__main__':unittest.main()
