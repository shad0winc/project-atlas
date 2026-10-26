from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('atlas_worker_environment_installer',ROOT/'install_worker_environment.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
ORIGINAL=(ROOT/'tests/fixtures/entrypoint_before_environment.sh').read_bytes()

class WorkerEnvironmentTests(unittest.TestCase):
    def staged(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        root=Path(folder.name);(root/'docker').mkdir()
        path=root/'docker/entrypoint.sh';path.write_bytes(ORIGINAL);path.chmod(0o755)
        return root,path
    def test_original_fixture_is_exact_upstream(self):
        self.assertEqual(hashlib.sha256(ORIGINAL).hexdigest(),installer.ENTRYPOINT_SHA256)
    def test_only_three_application_login_calls_change(self):
        fixed=installer.patched(ORIGINAL)
        self.assertEqual(fixed.count(installer.LOGIN_ARGUMENTS.encode()),3)
        restored=fixed
        for before,count in installer.CALLS:
            after=before.replace('su - ','su '+installer.LOGIN_ARGUMENTS+' ',1)
            self.assertEqual(restored.count(after.encode()),count)
            restored=restored.replace(after.encode(),before.encode())
        self.assertEqual(restored,ORIGINAL)
    def test_shell_syntax_remains_valid(self):
        result=subprocess.run(['bash','-n'],input=installer.patched(ORIGINAL),capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0)
    def test_install_is_idempotent_and_keeps_executable_mode(self):
        root,path=self.staged();installer.install(root);first=path.read_bytes()
        installer.install(root);self.assertEqual(path.read_bytes(),first)
        self.assertEqual(path.stat().st_mode&0o777,0o755)
    def test_unrelated_upstream_drift_refuses_without_write(self):
        root,path=self.staged();path.write_bytes(ORIGINAL+b'\n# unexpected\n');before=path.read_bytes()
        with self.assertRaises(AssertionError):installer.install(root)
        self.assertEqual(path.read_bytes(),before)
    def test_post_install_drift_refuses_without_write(self):
        root,path=self.staged();installer.install(root)
        path.write_bytes(path.read_bytes()+b'\n# unexpected\n');before=path.read_bytes()
        with self.assertRaises(AssertionError):installer.install(root)
        self.assertEqual(path.read_bytes(),before)
    def test_symlink_target_refused(self):
        root,path=self.staged();path.unlink();target=root/'outside.sh';target.write_bytes(ORIGINAL)
        path.symlink_to(target)
        with self.assertRaises(AssertionError):installer.install(root)
        self.assertEqual(target.read_bytes(),ORIGINAL)
    def test_whitelist_is_exact_and_contains_no_values_or_wildcards(self):
        self.assertEqual(set(installer.ENVIRONMENT_KEYS),{
            'ATLAS_SPORTS_PILOT_MODE','ATLAS_VERIFIED_LIVE_MODE','ATLAS_RESERVATION_LEDGER_MIGRATED',
            'ATLAS_SPORTS_POLICY_ORIGIN','ATLAS_SPORTS_LIVE_POLICY_TOKEN','ATLAS_VERIFIED_LIVE_SCOPE_KEY_FILE'})
        self.assertEqual(len(installer.ENVIRONMENT_KEYS),6)
        tokens=shlex.split('su '+installer.LOGIN_ARGUMENTS+' "$POSTGRES_USER"')
        self.assertEqual(tokens[:2],['su','--login'])
        self.assertEqual(tokens[2],'--whitelist-environment='+','.join(installer.ENVIRONMENT_KEYS))
        self.assertNotIn('*',tokens[2])
    def test_secret_values_are_not_serialized_into_script_or_profile(self):
        marker="fixture-'-$()-;\nprivate-token"
        before=installer.patched(ORIGINAL)
        with patch.dict(os.environ,{'ATLAS_SPORTS_LIVE_POLICY_TOKEN':marker}):
            after=installer.patched(ORIGINAL)
        self.assertEqual(before,after)
        self.assertNotIn(marker.encode(),after)
        prefix=ORIGINAL[:ORIGINAL.index(b'# Run init scripts')]
        self.assertEqual(after[:after.index(b'# Run init scripts')],prefix)

if __name__=='__main__':unittest.main()
