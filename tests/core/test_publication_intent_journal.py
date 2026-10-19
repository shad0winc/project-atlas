"""Real inherited exclusion, immutable intents and interrupted marker fencing."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from atlas.deployment_publication_journal import PublicationIntentJournal
from atlas.maintenance_control import MaintenanceAuthority, MaintenanceControlError

ROOT = Path(__file__).resolve().parents[2]


class PublicationIntentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.root = Path(self.temp.name)
        for name in ('maintenance','deployments','deployments/update.lock','deployments/records',
                     'deployments/records/baseline-old','deployments/records/update-failed',
                     'deployments/repairs','deployments/repairs/fixture','deployments/repairs/fixture/candidate'):
            (self.root/name).mkdir(mode=0o700)
        self.owner = self.root/'deployments/update.lock/owner';self.owner.write_bytes(b'deployment_id=update-failed\npid=123\n')
        self.owner_raw=self.owner.read_bytes();self.owner_info=self.owner.stat()
        (self.root/'maintenance/enabled').touch();self.current=self.root/'deployments/current';self.current.write_text('baseline-old\n')
        self.candidate=self.root/'deployments/repairs/fixture/candidate'
        for name,value in {'metadata':'fixture=1\n','status':'prepared\n','core-source.tar.gz':'synthetic archive\n','images.tsv':'synthetic images\n'}.items():
            (self.candidate/name).write_text(value)
        self.protected={}
        for record in ('baseline-old','update-failed'):
            for name in ('metadata','status'):
                path=self.root/'deployments/records'/record/name;path.write_text(record+'\n')
                self.protected[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(self.candidate.iterdir()))
        (self.candidate/'MANIFEST.sha256').write_text(manifest)
        self.arguments=dict(publication_id='reconciliation-new',expected_current='baseline-old',
            candidate_relative='deployments/repairs/fixture/candidate',candidate_manifest=hashlib.sha256(manifest.encode()).hexdigest(),
            evidence=self.protected)
        lock=self.root/'deployment-scheduler.lock';lock.touch(mode=0o600)
        self.stream=lock.open('r+');fcntl.flock(self.stream.fileno(),fcntl.LOCK_EX)
        self.journal=PublicationIntentJournal(self.root,'update-failed',self.stream.fileno())
        self.marker=self.root/'maintenance/publication-pending'
        self.folder=self.root/'deployments/publication-journals/reconciliation-new'

    def tearDown(self):
        self.assertEqual(self.owner.read_bytes(),self.owner_raw)
        self.assertEqual(self.owner.stat().st_ino,self.owner_info.st_ino)
        self.assertEqual(self.current.read_text(),'baseline-old\n')
        self.assertTrue((self.root/'maintenance/enabled').is_file())
        self.stream.close();self.temp.cleanup()

    def test_complete_intent_pins_owner_candidate_and_protected_records(self):
        digest=self.journal.begin(**self.arguments);intent=self.journal.inspect('reconciliation-new')
        self.assertEqual(intent['old_current'],'baseline-old')
        self.assertEqual(intent['original_owner']['file_inode'],self.owner_info.st_ino)
        self.assertEqual(intent['protected_evidence'],self.protected)
        self.assertEqual((self.folder/'original-lock-owner').read_bytes(),self.owner_raw)
        self.assertEqual(json.loads(self.marker.read_bytes())['intent_sha256'],digest)
        self.assertEqual(self.journal.begin(**self.arguments),digest)
        self.assertTrue(MaintenanceAuthority(self.root).status()['transition_pending'])

    def test_web_and_cli_cannot_reopen_a_pending_publication(self):
        self.journal.begin(**self.arguments)
        fcntl.flock(self.stream.fileno(),fcntl.LOCK_UN)
        for source in ('web','cli'):
            with self.assertRaises(MaintenanceControlError):MaintenanceAuthority(self.root).change(False,actor='admin',source=source)
        self.assertTrue(self.marker.exists())

    def test_publication_marker_blocks_reopen_even_if_owner_directory_is_absent(self):
        self.journal.begin(**self.arguments);fcntl.flock(self.stream.fileno(),fcntl.LOCK_UN)
        lock=self.root/'deployments/update.lock';retired=self.root/'deployments/fixture-retired-lock'
        lock.rename(retired)
        try:
            state=MaintenanceAuthority(self.root).status()
            self.assertFalse(state['recovery_held']);self.assertTrue(state['transition_pending'])
            with self.assertRaises(MaintenanceControlError):
                MaintenanceAuthority(self.root).change(False,actor='admin',source='web')
            self.assertTrue((retired/'owner').is_file());self.assertTrue(self.marker.is_file())
        finally:retired.rename(lock)

    def test_generic_host_repair_keeps_publication_marker(self):
        self.journal.begin(**self.arguments);fcntl.flock(self.stream.fileno(),fcntl.LOCK_UN)
        state=MaintenanceAuthority(self.root).recover_hold(actor='fixture-host')
        self.assertTrue(state['transition_pending']);self.assertTrue(self.marker.is_file())

    def test_conflicting_candidate_pin_is_refused_without_overwriting_intent(self):
        self.journal.begin(**self.arguments);before=(self.folder/'intent.json').read_bytes()
        changed={**self.arguments,'publication_id':'another-publication'}
        with self.assertRaises(MaintenanceControlError):self.journal.begin(**changed)
        self.assertEqual((self.folder/'intent.json').read_bytes(),before)

    def test_changed_protected_file_is_refused(self):
        self.journal.begin(**self.arguments)
        path=Path(next(iter(self.protected)));path.write_text('changed\n')
        with self.assertRaises(MaintenanceControlError):self.journal.inspect('reconciliation-new')

    def test_candidate_inventory_and_symlinks_are_refused(self):
        extra=self.candidate/'extra';extra.write_text('unrecorded')
        with self.assertRaises(MaintenanceControlError):self.journal.begin(**self.arguments)
        extra.unlink();target=self.candidate/'images.tsv';target.unlink();target.symlink_to(self.owner)
        with self.assertRaises((OSError,MaintenanceControlError)):self.journal.begin(**self.arguments)
        self.assertFalse(self.marker.exists())

    def test_missing_protected_baseline_or_failed_record_is_refused(self):
        changed={**self.arguments,'evidence':{}}
        with self.assertRaises(MaintenanceControlError):self.journal.begin(**changed)
        self.assertFalse(self.marker.exists())

    def test_symlink_publication_marker_fails_closed(self):
        self.marker.symlink_to(self.owner)
        self.assertTrue(MaintenanceAuthority(self.root).status()['state_uncertain'])
        with self.assertRaises(MaintenanceControlError):self.journal.begin(**self.arguments)

    def test_actual_exclusive_parent_is_mandatory(self):
        fcntl.flock(self.stream.fileno(),fcntl.LOCK_UN)
        with self.assertRaises(MaintenanceControlError):self.journal.begin(**self.arguments)
        self.assertFalse(self.marker.exists())

    def test_pending_marker_flush_failure_still_fences_reopen(self):
        with patch('atlas.deployment_publication_journal.os.fsync',side_effect=OSError('injected')):
            with self.assertRaises(MaintenanceControlError):self.journal.begin(**self.arguments)
        self.assertTrue(self.marker.exists())
        self.assertTrue(MaintenanceAuthority(self.root).status()['transition_pending'])
        with self.assertRaises((OSError,MaintenanceControlError)):self.journal.begin(**self.arguments)

    def test_owner_replacement_with_identical_bytes_is_refused(self):
        self.journal.begin(**self.arguments)
        saved=self.root/'saved-owner';self.owner.rename(saved);self.owner.write_bytes(self.owner_raw)
        try:
            with self.assertRaises(MaintenanceControlError):self.journal.inspect('reconciliation-new')
        finally:
            self.owner.unlink();saved.rename(self.owner)

    def test_evidence_change_during_intent_write_is_refused_and_fenced(self):
        def change(phase):
            if phase=='publication_owner_copy_durable':Path(next(iter(self.protected))).write_text('changed-during-intent\n')
        self.journal.checkpoint=change
        with self.assertRaises(MaintenanceControlError):self.journal.begin(**self.arguments)
        self.assertTrue(self.marker.is_file())

    def test_pointer_move_is_refused_and_not_reverted(self):
        self.journal.begin(**self.arguments);self.current.write_text('reconciliation-new\n')
        with self.assertRaises(MaintenanceControlError):self.journal.inspect('reconciliation-new')
        self.assertEqual(self.current.read_text(),'reconciliation-new\n')
        self.current.write_text('baseline-old\n')

    def test_actual_process_death_keeps_owner_and_marker_at_every_checkpoint(self):
        code='''import json,os,sys
from pathlib import Path
from atlas.deployment_publication_journal import PublicationIntentJournal
def stop(phase):
 if phase==sys.argv[3]:os._exit(79)
j=PublicationIntentJournal(Path(sys.argv[1]),'update-failed',int(sys.argv[2]),checkpoint=stop)
j.begin(**json.loads(sys.argv[4]))
'''
        for phase in ('publication_pending_durable','publication_owner_copy_durable','publication_intent_durable'):
            with self.subTest(phase=phase):
                result=subprocess.run([sys.executable,'-B','-c',code,str(self.root),str(self.stream.fileno()),phase,json.dumps(self.arguments)],
                    pass_fds=(self.stream.fileno(),),env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True)
                self.assertEqual(result.returncode,79,result.stderr)
                self.assertEqual(self.owner.read_bytes(),self.owner_raw)
                self.assertTrue(MaintenanceAuthority(self.root).status()['transition_pending'])
                if phase=='publication_intent_durable':
                    self.assertEqual(self.journal.inspect('reconciliation-new')['old_current'],'baseline-old')
                    self.journal.begin(**self.arguments)
                else:
                    with self.assertRaises((OSError,MaintenanceControlError)):self.journal.begin(**self.arguments)
                # Only the disposable test owner resets between independent kill cases.
                import shutil
                if self.folder.parent.exists():shutil.rmtree(self.folder.parent)
                self.marker.unlink()


if __name__=='__main__':unittest.main()
