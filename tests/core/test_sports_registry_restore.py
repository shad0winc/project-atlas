"""Real bounded row/revert engine and consumer contracts in non-production roots."""
import importlib.util
import contextlib
import io
import hashlib
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
def load(name,relative):
 spec=importlib.util.spec_from_file_location(name,ROOT/relative)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
support=load('registry_restore_test','scripts/lib/sports-registry-restore.py')
native=load('registry_restore_native_test','scripts/lib/sports-native-consumption.py')


def stage_fixture(root,optional=True):
 stage=root/'fixture';stage.mkdir(mode=0o700)
 support.populate({p:stage/p for s,p,r,k in support.SURFACES},optional=optional)
 support.manifest(stage,optional)
 (stage/'RECOVERY_FORMAT').write_text('1\n')
 (stage/'BACKUP_INFO.txt').write_text('Project Atlas private row-engine unit fixture\n')
 sums=[]
 for path in sorted((stage/'state').rglob('*')):
  if path.is_file():sums.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.relative_to(stage).as_posix())
 (stage/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
 for path in stage.rglob('*'):path.chmod(0o700 if path.is_dir() else 0o600)
 return stage


class RowEngine(unittest.TestCase):
 def test_all_sixteen_captured_restore_through_real_consumer_contracts(self):
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   stage=stage_fixture(Path(tmp));before=native.shape(stage,True)
   result=support.trial(native,stage)
   self.assertEqual(result['surfaces'],16);self.assertFalse(result['held'])
   self.assertEqual(native.shape(stage,True),before)

 def test_optional_absent_rows_remove_existing_old_values_and_validate(self):
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   stage=stage_fixture(Path(tmp),False)
   rows=support.consumer(stage)
   self.assertEqual(sum(row[0]=='SKIP' for row in rows),2)
   self.assertFalse(support.trial(native,stage)['held'])

 def test_partial_setup_and_each_completed_row_revert_without_releasing_maintenance(self):
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   stage=stage_fixture(Path(tmp));before=native.shape(stage,True)
   for boundary in range(17):
    with self.subTest(boundary=boundary):
     result=support.trial(native,stage,fail_after=boundary)
     self.assertTrue(result['held']);self.assertEqual(result['failed_after'],boundary)
   self.assertEqual(native.shape(stage,True),before)

 def test_failure_after_preparing_incoming_copy_reverts_prior_rows_and_stays_held(self):
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   stage=stage_fixture(Path(tmp));before=native.shape(stage,True)
   result=support.trial(native,stage,fail_copy=True)
   self.assertTrue(result['partial_copy'] and result['held'])
   self.assertEqual(native.shape(stage,True),before)

 def test_malformed_consumer_state_is_rejected_before_row_engine(self):
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   stage=stage_fixture(Path(tmp))
   (stage/'state/users/users.json').write_text('{"schema_version":1,"users":[]}\n')
   with self.assertRaises(ValueError):support.trial(native,stage)

 def test_cursor_beyond_captured_event_journal_is_rejected(self):
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   stage=stage_fixture(Path(tmp))
   (stage/'state/runtime/subscribers/module-notifications.cursor').write_text('2\n')
   with self.assertRaises(ValueError):support.consumer(stage)

 def test_plan_refuses_duplicate_surface_wrong_path_and_missing_required_state(self):
  with tempfile.TemporaryDirectory(prefix='atlas-registry-restore.',dir='/tmp') as tmp:
   root=Path(tmp);stage=stage_fixture(root);env=support.environment(root)
   original=(stage/'RECOVERY_MANIFEST.tsv').read_text()
   for text in (original+original.splitlines()[2]+'\n',
     original.replace('state/users','../../outside'),
     original.replace('users\tstate/users\trequired\tcaptured','users\tstate/users\trequired\tabsent-optional')):
    (stage/'RECOVERY_MANIFEST.tsv').write_text(text)
    with self.assertRaises(ValueError):support.plan(root,stage,env)
   (stage/'RECOVERY_MANIFEST.tsv').write_text(original)
   (stage/'state/users/users.json').unlink();(stage/'state/users').rmdir()
   with self.assertRaises(ValueError):support.plan(root,stage,env)

 def test_plan_destinations_are_exact_registry_paths_and_private(self):
  with tempfile.TemporaryDirectory(prefix='atlas-registry-restore.',dir='/tmp') as tmp:
   root=Path(tmp);stage=stage_fixture(root);env=support.environment(root)
   rows=support.plan(root,stage,env).splitlines()
   self.assertEqual(len(rows),16)
   for row in rows:
    fields=row.split('\t');self.assertEqual(len(fields),6)
    self.assertTrue(Path(fields[-1]).is_relative_to(root/'configs'))
   with self.assertRaises(ValueError):support.environment(Path('/mnt/storage/configs/atlas'))

 def test_boolean_boundary_and_out_of_range_refused(self):
  for value in (True,-2,17,'1'):
   with self.subTest(value=value),self.assertRaises(ValueError):support.trial(native,Path('/tmp/missing'),fail_after=value)

 def test_consumer_refusal_after_application_retains_rollback_and_held_maintenance(self):
  with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
   stage=stage_fixture(Path(tmp));before=native.shape(stage,True)
   result=support.trial(native,stage,reject_validation=True)
   self.assertTrue(result['validation_rejected'] and result['held'])
   self.assertEqual(native.shape(stage,True),before)


class CompleteArchiveEnvelope(unittest.TestCase):
 def test_real_format3_stage_all_consumers_failures_and_live_plan_refusal(self):
  previous=load('registry_unit_archive_fixture','tests/core/test_sports_backup_archive.py')
  fixture=previous.ArchiveTests('test_real_command_publishes_complete_format3_and_roundtrips_metadata')
  self.addCleanup(fixture.doCleanups);fixture.setUp()
  support.populate_archive(fixture.env)
  archive=previous.support.publish(native,fixture.env)
  before=previous.support.sha(archive)
  output=io.StringIO()
  with contextlib.redirect_stdout(output):support.accept_archive(native,archive,fixture.env)
  self.assertEqual(previous.support.sha(archive),before)
  self.assertIn('SIXTEEN_REGISTRY_REPLACEMENT_CONSUMER_VALIDATION_AND_FINALIZE=PASS',output.getvalue())
  self.assertIn('"production_format3_plan_blocked": true',output.getvalue())
  self.assertIn('"consumer_refusal_held": true',output.getvalue())


class CompositionGuards(unittest.TestCase):
 def test_parent_failure_restores_scoped_loader_and_never_claims_binding(self):
  from unittest.mock import patch
  original=support.refresh.writer.archive.load
  output=io.StringIO();rehearsal=support.Rehearsal()
  with patch.object(support.refresh.Rehearsal,'prepare_baseline',side_effect=ValueError('fixture refusal')):
   with contextlib.redirect_stdout(output),self.assertRaises(ValueError):
    rehearsal.prepare_baseline(None,None,None,None,None)
  self.assertIs(support.refresh.writer.archive.load,original)
  self.assertIsNone(rehearsal.registry_archive_sha)
  self.assertNotIn('BINDING=PASS',output.getvalue())

 def test_missing_registry_acceptance_cannot_pass_parent_success(self):
  from unittest.mock import patch
  rehearsal=support.Rehearsal()
  with patch.object(support.refresh.Rehearsal,'prepare_baseline',return_value=None):
   with self.assertRaises(ValueError):rehearsal.prepare_baseline(None,None,None,None,None)

 def test_archive_fixture_rewrite_refuses_production_roots_before_access(self):
  with self.assertRaises(ValueError):
   support.populate_archive({'PRIVATE_ROOT':'/mnt/storage/configs/atlas'})
