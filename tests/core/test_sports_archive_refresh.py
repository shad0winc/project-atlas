"""Real worker/bounded child/writer SIGTERM with local HTTP; Docker identity needs CT100."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]


def load(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


support=load('archive_refresh_test','scripts/lib/sports-archive-refresh.py')
native=load('archive_refresh_native_test','scripts/lib/sports-native-consumption.py')
previous=load('archive_refresh_broker_test','tests/core/test_sports_archive_broker.py')


class Guards(unittest.TestCase):
    def setUp(self):
        previous.RuntimeGuards.setUp(self)
        self.name='atlas-archive-refresh-'+self.identifier;self.row['Name']='/'+self.name
        self.row['Config']['Labels']={support.LABEL:self.identifier}
        self.row['Config']['Cmd']=['-B','-c',support.BOOTSTRAP]
        self.row['Config']['Env']=['ATLAS_FIXTURE_REFRESH_CASE=complete','ATLAS_SPORTS_METADATA_STATE_DIR=/metadata',
            'ATLAS_SPORTS_METADATA_REFRESH_FILE=/policy/refresh.json','ATLAS_SPORTS_WRITER_TOKEN='+support.writer.TOKEN]

    def inspect(self,row):
        return support.inspect_owned(SimpleNamespace(inspect=lambda name:row),self.name,self.identifier,self.root,'complete','b'*64)

    def test_exact_bootstrap_identity_environment_and_mounts_are_required(self):
        self.inspect(self.row);self.row['Mounts'].reverse();self.inspect(self.row)
        for key,value in [('User','0:0'),('Entrypoint',['sh']),('Cmd',['-c','pass']),('Env',[])]:
            row=copy.deepcopy(self.row);row['Config'][key]=value
            with self.subTest(field=key),self.assertRaises(ValueError):self.inspect(row)
        row=copy.deepcopy(self.row);row['HostConfig']['NetworkMode']='host'
        with self.assertRaises(ValueError):self.inspect(row)
        row=copy.deepcopy(self.row);row['Mounts'][0]['Source']='/mnt/storage/configs/atlas'
        with self.assertRaises(ValueError):self.inspect(row)

    def test_fixture_cases_keep_isolation_and_actual_bounded_child_bootstrap(self):
        for case in ('complete','deadline'):
            args=support.arguments(self.name,self.identifier,self.root,case)
            self.assertEqual(args[-4:],[support.writer.IMAGE,'-B','-c',support.BOOTSTRAP])
            self.assertIn('ATLAS_FIXTURE_REFRESH_CASE='+case,args)
            self.assertIn('--network=none',args);self.assertIn('--user=1000:1000',args)
        with self.assertRaises(ValueError):support.arguments(self.name,self.identifier,self.root,'other')

    def test_shutdown_receipt_refuses_leaked_children_or_new_admissions(self):
        for case in ('complete','deadline'):
            proof={'version':1,'case':case,'worker_stopped':True,'child_reaped':True,'paid_attempts':1,
                'fetch_children':1,'post_stop_tick_blocked':True,'reservation_visible':True,
                'failure_category':'deadline' if case=='deadline' else None,
                'production_state_access':False,'live_restore_enabled':False}
            support.validate_receipt(proof,case)
            for key,value in [('worker_stopped',False),('child_reaped',False),('paid_attempts',2),
                    ('fetch_children',2),('post_stop_tick_blocked',False),('production_state_access',True),('live_restore_enabled',True)]:
                changed=dict(proof);changed[key]=value
                with self.subTest(case=case,field=key),self.assertRaises(ValueError):support.validate_receipt(changed,case)

    def test_parent_failure_blocks_refresh_acceptance(self):
        with patch.object(support.broker.Rehearsal,'verify',side_effect=ValueError('fixture refusal')),patch.object(support,'accept') as accept:
            with self.assertRaises(ValueError):support.Rehearsal().verify(native,Path('/tmp/missing-refresh-unit'))
            accept.assert_not_called()


class RealRefreshShutdown(unittest.TestCase):
    def run_case(self,case):
        with tempfile.TemporaryDirectory(prefix='project-atlas-refresh-app-test.',dir='/tmp') as temporary:
            root=Path(temporary);source=root/'source';support.writer.stage_source(native,source)
            state=root/'state';state.mkdir(mode=0o700);support.writer.archive.metadata.create(native,root,'new')
            policy_before=native.pub.digest(root/'sports-metadata-policy',True)
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env={'PATH':os.environ['PATH'],'PYTHONPATH':str(source),'PYTHONDONTWRITEBYTECODE':'1',
                'ATLAS_FIXTURE_WRITER_PORT':str(port),'ATLAS_FIXTURE_REFRESH_CASE':case,
                'ATLAS_SPORTS_WRITER_TOKEN':support.writer.TOKEN,
                'ATLAS_SPORTS_METADATA_STATE_DIR':str(root/'sports-metadata'),
                'ATLAS_SPORTS_METADATA_REFRESH_FILE':str(root/'sports-metadata-policy/refresh.json'),
                **{key:str(state/value) for key,value in support.writer.REGISTRIES.items()}}
            process=subprocess.Popen([sys.executable,'-B','-c',support.BOOTSTRAP],cwd=source,env=env,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                deadline=time.monotonic()+6
                while not (state/'FETCH.json').exists():
                    self.assertIsNone(process.poll(),'refresh writer exited before fetch')
                    self.assertLess(time.monotonic(),deadline);time.sleep(.01)
                # The provider can enter before the writer begins serving HTTP.
                import urllib.request
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                while True:
                    try:
                        with opener.open('http://127.0.0.1:'+str(port)+'/health',timeout=.5) as response:
                            if response.status==200:break
                    except OSError:pass
                    self.assertLess(time.monotonic(),deadline);time.sleep(.01)
                probe='POLICY='+repr(support.POLICY)+'\n'+support.PREFLIGHT
                result=subprocess.run([sys.executable,'-B','-c',probe],cwd=source,env=env,capture_output=True,timeout=3)
                self.assertEqual(result.returncode,0,result.stderr.decode()[-2000:])
                started=time.monotonic();process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=15),0)
                self.assertLess(time.monotonic()-started,15)
                proof=json.loads((state/'SHUTDOWN.json').read_text());support.validate_receipt(proof,case)
                self.assertEqual(native.pub.digest(root/'sports-metadata-policy',True),policy_before)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=15)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)

    def test_sigterm_allows_inflight_completion_then_reaps_and_blocks_admission(self):self.run_case('complete')

    def test_sigterm_waits_for_real_fetch_deadline_kill_and_reap(self):self.run_case('deadline')


if __name__=='__main__':unittest.main()
