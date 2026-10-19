"""Actual journal, archive materialization, durable pointer and shell coordinator.

Only external runtime/Doctor/Verify checks are fixtures; no runtime is activated.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from atlas.deployment_held_publication import HeldPublication
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_publication_intent_journal as intent_fixtures
from tests.core.test_scheduler_runtime_source import _write_source_tree, _archive_source

ROOT=Path(__file__).resolve().parents[2]


class HeldPublicationTests(unittest.TestCase):
    def setUp(self):
        intent_fixtures.PublicationIntentTests.setUp(self)
        source=self.root/'archive-source';_write_source_tree(source)
        _archive_source(source,self.candidate/'core-source.tar.gz')
        (self.candidate/'metadata').write_text('deployment_id=reconciliation-new\ntype=baseline\nprevious_baseline=baseline-old\n')
        self.reseal()
        self.journal=HeldPublication(self.root,'update-failed',self.stream.fileno())
        self.journal.begin(**self.arguments)
        self.events=self.root/'events'

    def reseal(self):
        manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
                         for p in sorted(self.candidate.iterdir()) if p.name!='MANIFEST.sha256')
        (self.candidate/'MANIFEST.sha256').write_text(manifest)
        self.arguments['candidate_manifest']=hashlib.sha256(manifest.encode()).hexdigest()
        self.original_candidate={p.name:p.read_bytes() for p in self.candidate.iterdir()}

    def tearDown(self):
        self.assertIn(self.current.read_text(),('baseline-old\n','reconciliation-new\n'))
        self.assertEqual({p.name:p.read_bytes() for p in self.candidate.iterdir()},self.original_candidate)
        self.current.write_text('baseline-old\n')
        intent_fixtures.PublicationIntentTests.tearDown(self)

    def shell(self, point='success'):
        code=r'''
set -euo pipefail
source "$1"
original="$(declare -f atlas_deployment_set_current)"
eval "${original/atlas_deployment_set_current ()/fixture_real_set_current ()}"
doctors=0
atlas_deployment_validate_source() { echo source-guard >> "$ATLAS_TEST_EVENTS"; [[ "$ATLAS_TEST_POINT" != source_refused ]]; }
atlas_deployment_verify_runtime() {
  printf 'runtime:%s\n' "${1##*/}" >> "$ATLAS_TEST_EVENTS"
  [[ "$ATLAS_TEST_POINT" != record_runtime_refused || "$1" == */candidate ]]
}
atlas_command_doctor() {
  doctors=$((doctors+1));printf 'doctor:%s\n' "$doctors" >> "$ATLAS_TEST_EVENTS"
  [[ "$ATLAS_TEST_POINT" != private_refused || "$doctors" != 1 ]] || return 1
  [[ "$ATLAS_TEST_POINT" != post_pointer_refused || "$doctors" != 2 ]]
}
atlas_command_verify() { echo verify >> "$ATLAS_TEST_EVENTS"; }
atlas_deployment_capture_private_held_acceptance() {
  atlas_deployment_verify_runtime "$4" || return 1
  atlas_command_doctor || return 1
  atlas_command_verify || return 1
  echo /fixture/private-receipt-not-production-acceptance.json
}
atlas_deployment_release_lock() { echo FORBIDDEN_OWNER_RELEASE >> "$ATLAS_TEST_EVENTS";return 99; }
atlas_command_maintenance() { echo FORBIDDEN_MAINTENANCE_CHANGE >> "$ATLAS_TEST_EVENTS";return 99; }
atlas_deployment_set_current() {
  [[ "$ATLAS_TEST_POINT" != death_before_pointer ]] || kill -KILL "$$"
  [[ "$ATLAS_TEST_POINT" != pointer_refused ]] || return 1
  fixture_real_set_current "$@" || return 1
  [[ "$ATLAS_TEST_POINT" != death_after_pointer ]] || kill -KILL "$$"
}
atlas_deployment_publish_candidate_held update-failed reconciliation-new "$2"
'''
        env={**os.environ,'ATLAS_RUNTIME_CONFIG_DIR':str(self.root),'ATLAS_PROJECT_DIR':str(ROOT),
             'ATLAS_TEST_EVENTS':str(self.events),'ATLAS_TEST_POINT':point,'PYTHONDONTWRITEBYTECODE':'1'}
        env.pop('ATLAS_DEPLOYMENT_DIR',None)
        return subprocess.run(['bash','-c',code,'held-publication-test',str(ROOT/'scripts/commands/deployment.sh'),str(self.stream.fileno())],
            env=env,pass_fds=(self.stream.fileno(),),capture_output=True,text=True)

    def check_hold(self):
        self.assertEqual(self.owner.read_bytes(),self.owner_raw)
        self.assertTrue(self.marker.is_file());self.assertTrue((self.root/'maintenance/enabled').is_file())
        if self.events.exists():self.assertNotIn('FORBIDDEN_',self.events.read_text())
        with (self.root/'deployment-scheduler.lock').open() as probe:
            with self.assertRaises(BlockingIOError):fcntl.flock(probe.fileno(),fcntl.LOCK_SH|fcntl.LOCK_NB)

    def test_real_native_held_publication_and_repeat_keep_owner_and_marker(self):
        result=self.shell();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.current.read_text(),'reconciliation-new\n');self.check_hold()
        self.assertTrue((self.folder/'held-boundary.json').is_file())
        first=self.events.read_text();result=self.shell();self.assertEqual(result.returncode,0,result.stderr)
        extra=self.events.read_text()[len(first):]
        self.assertEqual(extra,'source-guard\nruntime:reconciliation-new\ndoctor:1\nverify\n')
        self.assertEqual(self.journal.state('reconciliation-new'),'current-published')
        self.check_hold()

    def test_canonical_source_refusal_precedes_any_publication_or_runtime_probe(self):
        result=self.shell('source_refused');self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.events.read_text(),'source-guard\n')
        self.assertFalse((self.root/'deployments/records/reconciliation-new').exists())
        self.assertEqual(self.current.read_text(),'baseline-old\n');self.check_hold()

    def test_private_gate_refusal_publishes_nothing(self):
        result=self.shell('private_refused');self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/'deployments/records/reconciliation-new').exists())
        self.assertEqual(self.current.read_text(),'baseline-old\n');self.check_hold()

    def test_record_runtime_refusal_keeps_baseline_and_new_evidence(self):
        result=self.shell('record_runtime_refused');self.assertNotEqual(result.returncode,0)
        self.assertTrue((self.root/'deployments/records/reconciliation-new').is_dir())
        self.assertEqual(self.current.read_text(),'baseline-old\n');self.check_hold()

    def test_pointer_refusal_keeps_baseline_and_held_record_for_explicit_resume(self):
        result=self.shell('pointer_refused');self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.current.read_text(),'baseline-old\n');self.check_hold()
        result=self.shell();self.assertEqual(result.returncode,0,result.stderr);self.check_hold()

    def test_post_pointer_refusal_never_observes_held_completion(self):
        result=self.shell('post_pointer_refused');self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.current.read_text(),'reconciliation-new\n')
        self.assertFalse((self.folder/'held-boundary.json').exists());self.check_hold()
        result=self.shell();self.assertEqual(result.returncode,0,result.stderr);self.check_hold()

    def test_abrupt_shell_death_on_both_sides_of_actual_pointer_is_resumable(self):
        # Kill before publication, resume through publication, then resume after
        # the pointer. No completed held-boundary note precedes either kill.
        result=self.shell('death_before_pointer');self.assertEqual(result.returncode,-9,result.stderr)
        self.assertEqual(self.current.read_text(),'baseline-old\n');self.check_hold()
        result=self.shell('death_after_pointer');self.assertEqual(result.returncode,-9,result.stderr)
        self.assertEqual(self.current.read_text(),'reconciliation-new\n');self.check_hold()
        result=self.shell();self.assertEqual(result.returncode,0,result.stderr);self.check_hold()

    def test_record_process_death_at_each_durable_boundary_is_resumable(self):
        import shutil
        code='''import os,sys
from pathlib import Path
from atlas.deployment_held_publication import HeldPublication
def stop(phase):
 if phase==sys.argv[3]:os._exit(83)
j=HeldPublication(Path(sys.argv[1]),'update-failed',int(sys.argv[2]),checkpoint=stop)
j.record('reconciliation-new')
'''
        target=self.root/'deployments/records/reconciliation-new'
        for phase in ('record_staged_durable','record_renamed','record_namespace_durable'):
            with self.subTest(phase=phase):
                result=subprocess.run([sys.executable,'-B','-c',code,str(self.root),str(self.stream.fileno()),phase],
                    pass_fds=(self.stream.fileno(),),env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True)
                self.assertEqual(result.returncode,83,result.stderr);self.check_hold()
                self.assertEqual(self.journal.state('reconciliation-new'),'before-current')
                self.journal.record('reconciliation-new')
                self.assertEqual((target/'status').read_text(),'verified\n')
                self.assertEqual(self.current.read_text(),'baseline-old\n')
                # Disposable test reset only; production recovery never removes evidence.
                shutil.rmtree(target);(self.folder/'record-observed.json').unlink()

    def test_existing_foreign_target_record_is_not_replaced(self):
        target=self.root/'deployments/records/reconciliation-new';target.mkdir();(target/'foreign').write_text('retain\n')
        with self.assertRaises(MaintenanceControlError):self.journal.record('reconciliation-new')
        self.assertEqual((target/'foreign').read_text(),'retain\n');self.check_hold()

    def test_partial_staging_is_preserved_and_not_adopted(self):
        stage=self.folder/'record-staging';stage.mkdir();(stage/'status').write_text('verified\n')
        with self.assertRaises(MaintenanceControlError):self.journal.record('reconciliation-new')
        self.assertEqual(list(p.name for p in stage.iterdir()),['status']);self.check_hold()

    def test_native_finalizer_is_not_in_public_dispatch_and_has_no_release(self):
        source=(ROOT/'scripts/commands/deployment.sh').read_text()
        body=source.split('atlas_deployment_publish_candidate_held() {',1)[1].split('\natlas_command_deployment()',1)[0]
        self.assertNotIn('atlas_deployment_release_lock',body)
        self.assertNotIn('atlas_command_maintenance',body)
        self.assertNotIn('publish_candidate_held',source.split('atlas_command_deployment() {',1)[1])


if __name__=='__main__':unittest.main()
