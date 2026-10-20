import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from atlas import deployment_authority_binding as binding
from atlas.maintenance_control import MaintenanceControlError

def sha(value):return hashlib.sha256(value).hexdigest()
class FakeProbe:
 def __init__(self,verifier,reader,record,extension):
  self.verifier,self.reader,self.record,self.extension=verifier,reader,record,extension
  self.target_fingerprint='a'*64
 def observe(self):return {'fingerprint':'absent','identity':'absent'}
 def preflight(self,*,require_unit=False):return {'require_unit':require_unit}
 def removed(self):return True
class BindingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
  self.record=self.root/'record';self.record.mkdir()
  values={binding.FILES[0]:b"def check_record(record):\n assert extension_module().MARKER=='verified'\ndef metadata(record):return {'runtime_provenance_schema':'2'}\n",
          binding.FILES[1]:b"MARKER='verified'\n"}
  self.pins={}
  for name,raw in values.items():
   (self.source/name).write_bytes(raw);self.pins[name]=sha(raw)
  files={'ingress-runtime-extension.json':json.dumps({'authority':{},'caddy':{}}).encode(),'maintenance-authority.service':b'unit'}
  manifest=''
  for name,raw in files.items():(self.record/name).write_bytes(raw);manifest+=sha(raw)+'  '+name+'\n'
  (self.record/'MANIFEST.sha256').write_text(manifest);self.manifest=sha(manifest.encode())
  self.mock=self.enterContext(patch.object(binding,'NativeAuthorityProbe',FakeProbe))
 def load(self):return binding.BoundAuthorityProbe(self.source,self.pins,self.record,self.manifest)
 def test_verified_bytes_offline_record_and_native_probe_are_bound(self):
  probe=self.load()
  self.assertIs(probe.reader.extension_module(),probe.verifier)
  self.assertIs(probe.verifier.query,binding.local_query)
  self.assertEqual(probe.observe(),{'fingerprint':'absent','identity':'absent'})
  self.assertEqual(probe.preflight(require_unit=True),{'require_unit':True});self.assertTrue(probe.removed())
 def test_wrong_source_hash_refuses_before_compilation_or_probe(self):
  (self.source/binding.FILES[0]).write_text('this is invalid Python and must never compile')
  with self.assertRaisesRegex(MaintenanceControlError,'source_checksum'):self.load()
 def test_offline_verifier_refusal_propagates_before_probe(self):
  file=self.source/binding.FILES[0];file.write_text('def check_record(record):raise ValueError("invalid offline record")\n')
  self.pins[file.name]=sha(file.read_bytes())
  with self.assertRaisesRegex(ValueError,'invalid offline record'):self.load()
 def test_record_tamper_refuses_every_probe_operation(self):
  probe=self.load();(self.record/'maintenance-authority.service').write_bytes(b'other')
  for operation in (probe.observe,probe.preflight,probe.removed):
   with self.assertRaisesRegex(MaintenanceControlError,'record_checksum'):operation()
 def test_source_tamper_after_loading_refuses_observation(self):
  probe=self.load();file=self.source/binding.FILES[1];file.write_bytes(file.read_bytes()+b'\n')
  with self.assertRaisesRegex(MaintenanceControlError,'source_checksum'):probe.observe()
 def test_extra_record_file_refuses(self):
  probe=self.load();(self.record/'extra').write_bytes(b'x')
  with self.assertRaisesRegex(MaintenanceControlError,'inventory'):probe.observe()
 def test_wrong_manifest_or_duplicate_entries_refuse(self):
  with self.assertRaisesRegex(MaintenanceControlError,'manifest_differs'):
   binding.BoundAuthorityProbe(self.source,self.pins,self.record,'b'*64)
  path=self.record/'MANIFEST.sha256';path.write_bytes(path.read_bytes()*2);self.manifest=sha(path.read_bytes())
  with self.assertRaisesRegex(MaintenanceControlError,'duplicate'):self.load()
 def test_symlink_hardlink_and_writable_source_refuse(self):
  file=self.source/binding.FILES[1];saved=file.read_bytes();file.unlink();file.symlink_to(self.source/binding.FILES[0])
  with self.assertRaisesRegex(MaintenanceControlError,'path_linked'):self.load()
  file.unlink();file.write_bytes(saved);os.link(file,self.root/'link')
  with self.assertRaisesRegex(MaintenanceControlError,'file_unsafe'):self.load()
  (self.root/'link').unlink();file.chmod(0o666)
  with self.assertRaisesRegex(MaintenanceControlError,'file_unsafe'):self.load()
 def test_only_exact_local_systemd_show_queries_are_executable(self):
  with patch.object(binding.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'query')) as run:
   self.assertEqual(binding.local_query(list(binding.QUERIES[0])),b'query')
   args,kwargs=run.call_args
   self.assertEqual(args[0][:4],['/usr/bin/systemctl','--system','--no-ask-password','--no-pager'])
   self.assertEqual(set(kwargs['env']),{'PATH','LANG','SYSTEMD_PAGER','SYSTEMD_COLORS'})
   self.assertEqual(kwargs['timeout'],30)
   run.reset_mock()
   for command in (['systemctl','start',binding.UNIT],['docker','ps'],['systemctl','show','other.service']):
    with self.assertRaisesRegex(MaintenanceControlError,'query_scope'):binding.local_query(command)
   run.assert_not_called()
 def test_query_failure_and_timeout_fail_without_exposing_stderr(self):
  with patch.object(binding.subprocess,'run',return_value=SimpleNamespace(returncode=1,stderr=b'secret')):
   with self.assertRaisesRegex(MaintenanceControlError,'query_failed'):binding.local_query(list(binding.QUERIES[1]))
  with patch.object(binding.subprocess,'run',side_effect=subprocess.TimeoutExpired('private',30)):
   with self.assertRaisesRegex(MaintenanceControlError,'query_uncertain'):binding.local_query(list(binding.QUERIES[1]))
if __name__=='__main__':unittest.main()
