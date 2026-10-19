"""Real source Git identity, record/generation/journal and gate logs.

Docker inspect responses are explicit fixtures. No production runtime is queried.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from atlas.deployment_private_acceptance import PrivateHeldAcceptance
from atlas.maintenance_control import MaintenanceControlError
from tests.core import test_held_publication_coordinator as fixtures

ROOT=Path(__file__).resolve().parents[2]


class PrivateAcceptanceBindingTests(unittest.TestCase):
    def reseal(self):
        (self.candidate/'images.tsv').write_text('core|compose.yml|fixture|api|/atlas-fixture|fixture:tag|sha256:'+'a'*64+'\n')
        fixtures.HeldPublicationTests.reseal(self)
    shell=fixtures.HeldPublicationTests.shell
    check_hold=fixtures.HeldPublicationTests.check_hold

    def setUp(self):
        fixtures.HeldPublicationTests.setUp(self)
        result=self.shell();self.assertEqual(result.returncode,0,result.stderr)
        self.source=self.root/'canonical';self.source.mkdir()
        shutil.copytree(ROOT/'atlas',self.source/'atlas',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        def git(*args):
            subprocess.run(['git','-C',str(self.source),*args],check=True,capture_output=True)
        shutil.copytree(ROOT/'scripts',self.source/'scripts',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copyfile(ROOT/'.gitignore',self.source/'.gitignore')
        git('init','-b','main');git('add','.gitignore','atlas','scripts')
        git('-c','user.name=Atlas fixture','-c','user.email=fixture@example.invalid','commit','-m','Fixture canonical acceptance source')
        self.providers=self.root/'provider.json'
        self.providers.write_text(json.dumps({'fixture':{'status':'healthy','refresh_state':'deferred',
            'last_success_at':datetime.now(timezone.utc).isoformat(),
            'refresh_snapshot':{'version':1,'maximum_age_seconds':900,'completed_request_count':1,'oldest_response_age_seconds':0}}}))
        self.rows=[{'Id':'b'*64,'Name':'/atlas-fixture','Image':'sha256:'+'a'*64,'RestartCount':2,
            'Config':{'Env':['TOKEN=SUPER_SECRET']},'HostConfig':{'Binds':['/private/SUPER_SECRET:/data']},
            'Mounts':[{'Source':'/private/SUPER_SECRET','RW':False}],
            'State':{'Running':True,'Paused':False,'Restarting':False,'OOMKilled':False,'Pid':123,
                     'StartedAt':'fixture-started','Health':{'Status':'healthy','Log':[{'Output':'SUPER_SECRET'}]}}}]
        import importlib.util,sys
        spec=importlib.util.spec_from_file_location('fixture_canonical_acceptance',self.source/'atlas/deployment_private_acceptance.py')
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        self.acceptance=module.PrivateHeldAcceptance(self.root,'update-failed',self.stream.fileno())
        original=self.acceptance._command
        self.acceptance._command=lambda *args:json.dumps(self.rows).encode() if args[0]=='docker' else original(*args)

    def tearDown(self):fixtures.HeldPublicationTests.tearDown(self)

    def start(self):return self.acceptance.start('reconciliation-new',self.source,self.providers)

    def logs(self,attempt):
        for stage,text in {'runtime':'','doctor':'  OK runtime: good\n  OK provider: usable\nOverall Status: HEALTHY\n',
                           'verify':'Overall Status: PASS\n'}.items():
            (attempt/(stage+'.log')).write_text(text);(attempt/(stage+'.exit')).write_text('0\n')

    def finish(self,attempt):return self.acceptance.finish('reconciliation-new',attempt.name)

    def test_generated_bytecode_is_ignored_but_untracked_source_is_refused(self):
        import py_compile
        target=self.source/'atlas/deployment_private_acceptance.py'
        bytecode=Path(py_compile.compile(str(target),doraise=True))
        self.assertTrue(bytecode.is_file())
        status=subprocess.run(['git','-C',str(self.source),'status','--porcelain','--untracked-files=all'],
                              check=True,capture_output=True).stdout
        self.assertEqual(status,b'')
        self.acceptance._source(self.source)
        (self.source/'untracked-acceptance-source.py').write_text('unreviewed = True\n')
        with self.assertRaises(MaintenanceControlError):self.acceptance._source(self.source)

    def test_native_capture_writes_bound_logs_through_real_collector_cli(self):
        bin_dir=self.root/'bin';bin_dir.mkdir();runtime=self.root/'docker-inspect.json';runtime.write_text(json.dumps(self.rows))
        docker=bin_dir/'docker'
        docker.write_text('#!/usr/bin/env python3\nimport json,os,sys\nassert sys.argv[1:]==["inspect","atlas-fixture"]\nprint(open(os.environ["FIXTURE_INSPECT_JSON"]).read())\n')
        docker.chmod(0o755)
        code=r'''
set -euo pipefail
source "$1"
atlas_deployment_verify_runtime() { echo runtime-fixture; }
atlas_command_doctor() { printf '  OK runtime: fixture\nOverall Status: HEALTHY\n'; }
atlas_command_verify() { echo 'Overall Status: PASS'; }
atlas_deployment_capture_private_held_acceptance update-failed reconciliation-new "$2" "$ATLAS_RUNTIME_CONFIG_DIR/deployments/records/reconciliation-new"
'''
        env={**os.environ,'PATH':str(bin_dir)+os.pathsep+os.environ['PATH'],'PYTHONPATH':str(ROOT),
            'PYTHONDONTWRITEBYTECODE':'1','ATLAS_RUNTIME_CONFIG_DIR':str(self.root),'ATLAS_PROJECT_DIR':str(self.source),
            'SPORTS_PROVIDER_HEALTH_FILE':str(self.providers),
            'FIXTURE_SOURCE':str(self.source),'FIXTURE_PROVIDER':str(self.providers),'FIXTURE_INSPECT_JSON':str(runtime)}
        result=subprocess.run(['bash','-c',code,'capture-test',str(self.source/'scripts/commands/deployment.sh'),str(self.stream.fileno())],
            cwd=ROOT,pass_fds=(self.stream.fileno(),),env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        receipt=Path(result.stdout.strip());value=json.loads(receipt.read_bytes())
        self.assertTrue(value['accepted_private']);self.assertFalse(value['owner_release_permitted'])
        self.assertEqual({key:row['exit_code'] for key,row in value['stages'].items()},{'runtime':0,'doctor':0,'verify':0})
        self.check_hold()

    def test_exact_private_receipt_is_hash_bound_fresh_and_contains_no_provider_secrets(self):
        attempt=self.start();self.logs(attempt);receipt=self.finish(attempt)
        raw=receipt.read_bytes();value=json.loads(raw)
        self.assertTrue(value['accepted_private'])
        for name in ('owner_release_permitted','public_acceptance_proven','ci_acceptance_proven'):self.assertIs(value[name],False)
        self.assertNotIn(b'SUPER_SECRET',raw)
        self.assertEqual(set(value['context']['runtime']),{'atlas-fixture'})
        self.assertEqual(value['context']['runtime']['atlas-fixture']['restarts'],2)
        self.acceptance.validate('reconciliation-new',attempt.name,hashlib.sha256(raw).hexdigest())
        self.check_hold()

    def test_runtime_replacement_or_mount_drift_refuses_receipt(self):
        attempt=self.start();self.logs(attempt);self.rows[0]['Mounts'][0]['RW']=True
        with self.assertRaises(MaintenanceControlError):self.finish(attempt)
        self.assertFalse((attempt/'receipt.json').exists());self.check_hold()

    def test_container_restart_and_unhealthy_health_refuse_receipt(self):
        attempt=self.start();self.logs(attempt);self.rows[0]['RestartCount']+=1
        with self.assertRaises(MaintenanceControlError):self.finish(attempt)
        self.rows[0]['RestartCount']-=1;self.rows[0]['State']['Health']['Status']='unhealthy'
        with self.assertRaises(MaintenanceControlError):self.finish(attempt)

    def test_wrong_image_and_duplicate_inventory_are_refused_before_attempt(self):
        old=copy.deepcopy(self.rows);self.rows[0]['Image']='sha256:'+'c'*64
        with self.assertRaises(MaintenanceControlError):self.start()
        self.rows=old+[copy.deepcopy(old[0])]
        with self.assertRaises(MaintenanceControlError):self.start()

    def test_zero_exit_cannot_hide_doctor_warning_or_verify_failure(self):
        attempt=self.start();self.logs(attempt)
        (attempt/'doctor.log').write_text('  WARN storage: uncertain\nOverall Status: HEALTHY\n')
        with self.assertRaises(MaintenanceControlError):self.finish(attempt)
        self.logs(attempt);(attempt/'verify.log').write_text('FAIL storage\nOverall Status: PASS\n')
        with self.assertRaises(MaintenanceControlError):self.finish(attempt)

    def test_gate_exit_failure_and_missing_logs_are_not_accepted(self):
        attempt=self.start();self.logs(attempt);(attempt/'runtime.exit').write_text('1\n')
        with self.assertRaises(MaintenanceControlError):self.finish(attempt)
        (attempt/'runtime.exit').write_text('0\n');(attempt/'doctor.log').unlink()
        with self.assertRaises((OSError,MaintenanceControlError)):self.finish(attempt)

    def test_dirty_or_different_branch_source_is_refused(self):
        (self.source/'untracked').write_text('unreviewed')
        with self.assertRaises(MaintenanceControlError):self.start()
        (self.source/'untracked').unlink()
        subprocess.run(['git','-C',str(self.source),'checkout','-b','feature-not-promoted'],check=True,capture_output=True)
        with self.assertRaises(MaintenanceControlError):self.start()

    def test_reboot_expiry_and_clock_rollback_refuse_receipt(self):
        attempt=self.start();self.logs(attempt)
        with patch.object(self.acceptance,'_boot',return_value='different-boot'):
            with self.assertRaises(MaintenanceControlError):self.finish(attempt)
        import time
        now=time.time()
        for changed in (now+301,now-301):
            with patch('atlas.deployment_private_acceptance.time.time',return_value=changed):
                with self.assertRaises(MaintenanceControlError):self.finish(attempt)

    def test_provider_progress_is_allowed_but_unusable_snapshot_is_refused(self):
        attempt=self.start();self.logs(attempt)
        row=json.loads(self.providers.read_bytes());row['fixture']['last_success_at']=datetime.now(timezone.utc).isoformat()
        self.providers.write_text(json.dumps(row));receipt=self.finish(attempt);self.assertTrue(receipt.exists())
        row['fixture']['refresh_snapshot']['oldest_response_age_seconds']=901;self.providers.write_text(json.dumps(row))
        with self.assertRaises(MaintenanceControlError):self.acceptance.validate('reconciliation-new',attempt.name,hashlib.sha256(receipt.read_bytes()).hexdigest())

    def test_post_receipt_context_and_log_changes_invalidate_reuse(self):
        attempt=self.start();self.logs(attempt);receipt=self.finish(attempt);sha=hashlib.sha256(receipt.read_bytes()).hexdigest()
        (attempt/'verify.log').write_text('changed')
        with self.assertRaises(MaintenanceControlError):self.acceptance.validate('reconciliation-new',attempt.name,sha)
        self.logs(attempt);self.rows[0]['Config']['Env']=['TOKEN=ROTATED']
        with self.assertRaises(MaintenanceControlError):self.acceptance.validate('reconciliation-new',attempt.name,sha)

    def test_receipt_cannot_be_reissued_or_replaced_under_the_same_attempt(self):
        attempt=self.start();self.logs(attempt);receipt=self.finish(attempt);raw=receipt.read_bytes()
        with self.assertRaises(MaintenanceControlError):self.finish(attempt)
        self.assertEqual(receipt.read_bytes(),raw)

    def test_generation_file_drift_is_detected_after_native_publication(self):
        attempt=self.start();self.logs(attempt)
        path=self.root/'source/generations/reconciliation-new/VERSION';path.chmod(0o644);path.write_text('changed\n')
        with self.assertRaises(MaintenanceControlError):self.finish(attempt)


if __name__=='__main__':unittest.main()
