"""Writer runtime guards and real app startup; Docker/mapped UID acceptance is CT100."""
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
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


support = load('writer_archive_test', 'scripts/lib/sports-archive-writer.py')
native = load('writer_archive_native_test', 'scripts/lib/sports-native-consumption.py')


class WriterGuards(unittest.TestCase):
    def setUp(self):
        self.identifier = 'a'*32; self.name = 'atlas-archive-writer-'+self.identifier
        self.root = Path('/tmp/project-atlas-writer-runtime.unit')
        self.row = {'Id': 'b'*64, 'Name': '/'+self.name, 'Image': support.IMAGE,
            'Config': {'Labels': {support.LABEL: self.identifier}, 'User': '1000:1000',
                'Entrypoint': None, 'Cmd': ['python3', '/srv/sports/private_api.py'], 'WorkingDir': '/srv/sports'},
            'HostConfig': {'ReadonlyRootfs': True, 'NetworkMode': 'none', 'CapDrop': ['ALL'],
                'SecurityOpt': ['no-new-privileges:true'], 'RestartPolicy': {'Name': 'no'},
                'Tmpfs': {'/tmp': 'rw,nosuid,nodev,size=16m,mode=1777'}, 'IpcMode': 'private',
                'LogConfig': {'Type': 'none'}, 'Memory': 128*1024**2, 'PidsLimit': 64},
            'Mounts': [{'Type': 'bind', 'Source': str(self.root/source), 'Destination': destination, 'RW': rw}
                for source,destination,rw in [('source','/srv/sports',False),('state','/state',True),
                    ('sports-metadata','/metadata',True),('sports-metadata-policy','/policy',False)]]}

    def inspect(self, row):
        return support.inspect_owned(SimpleNamespace(inspect=lambda name: row), self.name, self.identifier, self.root, 'b'*64)

    def test_arguments_preserve_actual_command_and_isolate_mounts_network_identity(self):
        args = support.arguments(self.name, self.identifier, self.root)
        self.assertEqual(args[-1], support.IMAGE)
        self.assertNotIn('--entrypoint', args)
        for value in ('--network=none','--read-only','--user=1000:1000','--cap-drop=ALL','--pull=never'):
            self.assertIn(value, args)
        self.assertFalse(any(value.startswith(('--publish', '--privileged', '--env-file')) for value in args))
        self.assertIn('type=bind,source='+str(self.root/'sports-metadata-policy')+',destination=/policy,readonly', args)

    def test_complete_mount_records_accept_reordering_only(self):
        self.inspect(self.row)
        self.row['Mounts'].reverse(); self.inspect(self.row)
        self.row['Mounts'][0]['RW'] = True
        with self.assertRaises(ValueError): self.inspect(self.row)

    def test_unsafe_runtime_identity_network_command_or_mount_refused(self):
        changes = [('Id','c'*64), ('Image','sha256:'+'0'*64), ('Name','/atlas-sports-writer')]
        for key,value in changes:
            row = copy.deepcopy(self.row); row[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError): self.inspect(row)
        for key,value in [('NetworkMode','host'),('ReadonlyRootfs',False),('CapAdd',['SYS_ADMIN']),
                ('GroupAdd',['0']),('PortBindings',{'8003/tcp':[{'HostPort':'8003'}]}),
                ('UsernsMode','host'),('Privileged',True),('Tmpfs',{'/extra':'rw'})]:
            row=copy.deepcopy(self.row); row['HostConfig'][key]=value
            with self.subTest(field=key), self.assertRaises(ValueError): self.inspect(row)
        for key,value in [('User','0:0'),('Cmd',['python3','-c','pass']),('Entrypoint',['sh']),('Volumes',{'/extra':{}})]:
            row=copy.deepcopy(self.row); row['Config'][key]=value
            with self.subTest(field=key), self.assertRaises(ValueError): self.inspect(row)
        row=copy.deepcopy(self.row); row['Mounts'][0]['Source']='/opt/project-atlas'
        with self.assertRaises(ValueError): self.inspect(row)
        row=copy.deepcopy(self.row); row['Mounts'].append(copy.deepcopy(row['Mounts'][0]))
        with self.assertRaises(ValueError): self.inspect(row)

    def test_name_and_scope_are_guarded(self):
        for name,identifier,root in [('atlas-sports-writer',self.identifier,self.root),
                (self.name,'bad',self.root),(self.name,self.identifier,Path('/opt/project-atlas'))]:
            with self.assertRaises(ValueError): support.arguments(name,identifier,root)

    def test_only_normal_exit_zero_counts_as_acceptance(self):
        state={'Status':'exited','Running':False,'Pid':0,'ExitCode':0,'OOMKilled':False}
        support.stopped({'State':state})
        for key,value in [('ExitCode',137),('ExitCode',143),('Running',True),('Pid',1),('OOMKilled',True)]:
            row=dict(state);row[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):support.stopped({'State':row})

    def test_writer_acceptance_cannot_run_before_archive_verification(self):
        run=support.Rehearsal()
        with patch.object(support, 'accept') as accept:
            with self.assertRaises(ValueError):run.verify(native,Path('/tmp/missing-writer-unit'))
            accept.assert_not_called()


class RealApplicationStartup(unittest.TestCase):
    def test_packaged_source_http_auth_disabled_refresh_and_normal_restart(self):
        with tempfile.TemporaryDirectory(prefix='project-atlas-writer-app-test.',dir='/tmp') as temporary:
            root=Path(temporary); source=root/'source'; support.stage_source(native,source)
            self.assertEqual({p.name for p in source.iterdir()},set(support.source_inputs()))
            for name, original in support.source_inputs().items():
                self.assertEqual(native.shape(source/name,original.is_dir()),native.shape(original,original.is_dir()))
            state=root/'state';state.mkdir(mode=0o700)
            policy=root/'refresh.json';policy.write_text('{"version":1,"enabled":false}\n');policy.chmod(0o600)
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env={'PATH':os.environ['PATH'],'PYTHONPATH':str(source),'PYTHONDONTWRITEBYTECODE':'1',
                'ATLAS_SPORTS_WRITER_TOKEN':support.TOKEN,'ATLAS_SPORTS_METADATA_REFRESH_FILE':str(policy),
                **{key:str(state/value) for key,value in support.REGISTRIES.items()}}
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def get(path,token=None):
                request=urllib.request.Request('http://127.0.0.1:'+str(port)+path)
                if token is not None:request.add_header('Authorization','Bearer '+token)
                try:response=opener.open(request,timeout=1)
                except urllib.error.HTTPError as error:response=error
                with response:return response.status,json.loads(response.read(16384))
            shapes=[]
            for iteration in range(2):
                process=subprocess.Popen([sys.executable,'-B',str(source/'private_api.py'),'--port',str(port)],
                    cwd=source,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    deadline=time.monotonic()+10
                    while True:
                        self.assertIsNone(process.poll(),'writer exited before readiness')
                        try:
                            if get('/health')==(200,{'status':'ok'}):break
                        except (OSError,urllib.error.URLError):pass
                        self.assertLess(time.monotonic(),deadline);time.sleep(0.02)
                    self.assertEqual(get('/internal/v1/metadata/refresh-status')[0],401)
                    self.assertEqual(get('/internal/v1/metadata/refresh-status','wrong')[0],401)
                    self.assertEqual(get('/internal/v1/metadata/refresh-status',support.TOKEN),
                        (200,{'version':1,'state':'disabled','running':False}))
                    self.assertEqual(get('/internal/v1/metadata/day?route=football/nfl&day=2026-10-17',support.TOKEN)[0],503)
                    shapes.append(native.shape(state,True))
                    self.assertTrue(all((state/name).is_file() for name in support.REGISTRIES.values()))
                    process.send_signal(signal.SIGTERM);self.assertEqual(process.wait(timeout=5),0)
                finally:
                    if process.poll() is None:process.kill();process.wait(timeout=5)
            self.assertEqual(shapes[0],shapes[1])
            self.assertEqual(policy.read_text(),'{"version":1,"enabled":false}\n')


if __name__=='__main__':unittest.main()
