"""Actual writer/broker/loopback HTTP and persistent SQLite; Docker identity needs CT100."""
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
import urllib.request

ROOT=Path(__file__).resolve().parents[2]


def load(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


support=load('archive_broker_test','scripts/lib/sports-archive-broker.py')
native=load('archive_broker_native_test','scripts/lib/sports-native-consumption.py')
previous=load('archive_broker_writer_test','tests/core/test_sports_archive_writer.py')


class RuntimeGuards(unittest.TestCase):
    def setUp(self):
        previous.WriterGuards.setUp(self)
        self.name='atlas-archive-broker-'+self.identifier
        self.row['Name']='/'+self.name
        self.row['Config']['Labels']={support.LABEL:self.identifier}
        self.row['Config']['Entrypoint']=['python3'];self.row['Config']['Cmd']=['-B','-c',support.BOOTSTRAP]

    def inspect(self,row):
        return support.inspect_owned(SimpleNamespace(inspect=lambda name:row),self.name,self.identifier,self.root,'b'*64)

    def test_owned_bootstrap_and_exact_mounts_accept_order_changes(self):
        self.inspect(self.row);self.row['Mounts'].reverse();self.inspect(self.row)
        self.row['Mounts'][0]['RW']=True
        with self.assertRaises(ValueError):self.inspect(self.row)

    def test_wrong_bootstrap_network_identity_or_mount_is_refused(self):
        for key,value in [('Entrypoint',['sh']),('Cmd',['-c','pass']),('User','0:0')]:
            row=copy.deepcopy(self.row);row['Config'][key]=value
            with self.subTest(field=key),self.assertRaises(ValueError):self.inspect(row)
        row=copy.deepcopy(self.row);row['HostConfig']['NetworkMode']='host'
        with self.assertRaises(ValueError):self.inspect(row)
        row=copy.deepcopy(self.row);row['Id']='c'*64
        with self.assertRaises(ValueError):self.inspect(row)
        row=copy.deepcopy(self.row);row['Mounts'][0]['Source']='/mnt/storage/configs/atlas'
        with self.assertRaises(ValueError):self.inspect(row)

    def test_create_arguments_keep_network_isolation_and_pin_fixture_bootstrap(self):
        args=support.arguments(self.name,self.identifier,self.root)
        self.assertEqual(args[-4:],[support.writer.IMAGE,'-B','-c',support.BOOTSTRAP])
        self.assertIn('--network=none',args);self.assertIn('--read-only',args);self.assertIn('--user=1000:1000',args)
        self.assertEqual(args[args.index('--entrypoint')+1],'python3')
        self.assertEqual(args[args.index('--label')+1],support.LABEL+'='+self.identifier)

    def test_invalid_accounting_receipt_is_refused(self):
        data={'version':1,'paid_attempts':1,'provider_requests':1,'reservation_visible':True,
            'cache_reused':True,'budget_refused':True,'restart':False,'refresh_enabled':False}
        support.receipt(data,False)
        for key,value in [('paid_attempts',2),('provider_requests',2),('reservation_visible',False),
                ('cache_reused',False),('budget_refused',False),('restart',True),('refresh_enabled',True)]:
            changed=dict(data);changed[key]=value
            with self.subTest(field=key),self.assertRaises(ValueError):support.receipt(changed,False)

    def test_parent_verification_failure_blocks_broker_acceptance(self):
        with patch.object(support.writer.Rehearsal,'verify',side_effect=ValueError('fixture refusal')),patch.object(support,'accept') as accept:
            with self.assertRaises(ValueError):support.Rehearsal().verify(native,Path('/tmp/missing-broker-unit'))
            accept.assert_not_called()


class RealBrokerApplication(unittest.TestCase):
    def test_authenticated_requests_reserve_before_provider_reuse_cache_and_persist_budget(self):
        with tempfile.TemporaryDirectory(prefix='project-atlas-broker-app-test.',dir='/tmp') as temporary:
            root=Path(temporary);source=root/'source';support.writer.stage_source(native,source)
            state=root/'state';state.mkdir(mode=0o700)
            metadata=support.writer.archive.metadata
            metadata.create(native,root,'new')
            originals={key:native.pub.digest(root/key,True) for key in ('sports-metadata','sports-metadata-policy')}
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env={'PATH':os.environ['PATH'],'PYTHONPATH':str(source),'PYTHONDONTWRITEBYTECODE':'1',
                'ATLAS_FIXTURE_WRITER_PORT':str(port),'ATLAS_SPORTS_WRITER_TOKEN':support.writer.TOKEN,
                'ATLAS_SPORTS_METADATA_STATE_DIR':str(root/'sports-metadata'),
                'ATLAS_SPORTS_METADATA_REFRESH_FILE':str(root/'sports-metadata-policy/refresh.json'),
                **{key:str(state/value) for key,value in support.writer.REGISTRIES.items()}}
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));states=[]
            for attempt in range(2):
                process=subprocess.Popen([sys.executable,'-B','-c',support.BOOTSTRAP],cwd=source,env=env,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    deadline=time.monotonic()+10
                    while True:
                        self.assertIsNone(process.poll(),'broker writer exited before readiness')
                        try:
                            with opener.open('http://127.0.0.1:'+str(port)+'/health',timeout=1) as response:
                                if response.status==200:break
                        except OSError:pass
                        self.assertLess(time.monotonic(),deadline);time.sleep(.02)
                    result=subprocess.run([sys.executable,'-B','-c',support.CHECKS,'first' if attempt==0 else 'restart'],
                        cwd=source,env=env,capture_output=True,timeout=10)
                    self.assertEqual(result.returncode,0,result.stderr.decode()[-2000:])
                    support.receipt(json.loads(result.stdout),attempt==1)
                    process.send_signal(signal.SIGTERM);self.assertEqual(process.wait(timeout=5),0)
                    states.append((native.shape(state,True),native.shape(root/'sports-metadata',True)))
                finally:
                    if process.poll() is None:process.kill();process.wait(timeout=5)
            self.assertEqual(states[0],states[1])
            self.assertNotEqual(native.pub.digest(root/'sports-metadata',True),originals['sports-metadata'])
            self.assertEqual(native.pub.digest(root/'sports-metadata-policy',True),originals['sports-metadata-policy'])
            self.assertEqual(len((state/'provider-requests.jsonl').read_text().splitlines()),1)


if __name__=='__main__':unittest.main()
