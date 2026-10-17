"""Docker contract failures must precede fixture recovery or unsafe mutations."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


fence = load('lifecycle_test', 'scripts/lib/sports-recovery-lifecycle.py')
fixture = load('lifecycle_fixture', 'scripts/diagnostics/sports-recovery-consumption-drill.py')


class Docker:
    def __init__(self):
        self.identifier = 'a'*32; self.apps = {}; self.volumes = {}; self.calls = []
        self.pg = 'in production'; self.extra = set(); self.available = True
        for index, role in enumerate(fence.IMAGES, 1):
            name, data = fence.names(self.identifier, role); target = str(index)*64
            self.volumes[data] = {'Name': data, 'Driver': 'local', 'Scope': 'local',
                'Options': None, 'Labels': {fence.LABEL: self.identifier}}
            self.apps[target] = {'Id': target, 'Name': '/'+name, 'Image': fence.IMAGES[role], 'RestartCount': 0,
                'Config': {'Labels': {fence.LABEL: self.identifier}, 'User': '0:0', 'Cmd': ['app'], 'Entrypoint': None},
                'HostConfig': {'NetworkMode': 'none', 'RestartPolicy': {'Name': 'no'}, 'IpcMode': 'private', 'Tmpfs': {'/tmp': 'rw'}},
                'State': {'Status': 'running', 'Running': True, 'Pid': index+100, 'ExitCode': 0,
                    'StartedAt': '2026-10-17T01:00:00Z', 'OOMKilled': False},
                'Mounts': [{'Type': 'volume', 'Name': data, 'Destination': fence.DESTINATIONS[role], 'RW': True}]}

    def command(self, *args, timeout=30):
        self.calls.append(args)
        if not self.available: raise fence.LifecycleError('daemon unavailable')
        if args[0] == 'info': return 'test-daemon'
        if args[:2] == ('volume', 'inspect'): return json.dumps([self.volumes[args[2]]])
        if args[:2] == ('image', 'inspect'):
            return json.dumps([{'Id': args[2], 'Config': {'Cmd': ['app'], 'Entrypoint': None}}])
        if args[0] == 'inspect':
            items = [item for key, item in self.apps.items() if args[1] in (key, item['Name'][1:])]
            return json.dumps(items)
        if args[0] == 'ps':
            if '--filter' in args:
                data = args[args.index('--filter')+1].split('=', 1)[1]
                return '\n'.join([key for key, item in self.apps.items() if item['Mounts'][0]['Name'] == data] + sorted(self.extra))
            return '\n'.join(key+'|'+item['Name'][1:] for key, item in self.apps.items())
        if args[0] == 'exec':
            if '/usr/lib/postgresql/17/bin/pg_controldata' in args: return 'Database cluster state: '+self.pg
            if '/usr/lib/postgresql/17/bin/pg_ctl' in args: self.pg = 'shut down'; return ''
        if args[0] == 'stop':
            self.apps[args[-1]]['State'].update(Status='exited', Running=False, Pid=0); return args[-1]
        if args[0] == 'rm': del self.apps[args[1]]; return args[1]
        raise AssertionError(args)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp')
        self.root = Path(self.temp.name); self.original = fixture.fixture(self.root)
        fence.consumption.arm(self.root); fixture.mutate(self.root)
        self.docker = Docker(); self.mock = patch.object(fence, 'command', self.docker.command); self.mock.start()

    def tearDown(self):
        self.mock.stop(); self.temp.cleanup()

    def arm(self): fence.arm(self.root, self.docker.identifier)

    def test_detach_then_recover_twice_preserves_modified_state(self):
        self.arm()
        with self.assertRaises(fence.LifecycleError): fence.recover(self.root)
        fence.detach(self.root); fence.detach(self.root)
        fence.recover(self.root); fence.recover(self.root); fixture.verify(self.root, self.original)
        self.assertFalse(self.docker.apps); self.assertEqual(len(self.docker.volumes), 2)
        self.assertEqual(len([row for row in self.docker.calls if row[0] == 'rm']), 2)
        self.assertFalse(any('--force' in row or '--volumes' in row for row in self.docker.calls))

    def test_production_and_unscoped_identifiers_rejected(self):
        for identifier in ('atlas-dispatcharr', '../production', 'a'*31, 'A'*32, ''):
            with self.subTest(identifier=identifier), self.assertRaises(fence.LifecycleError):
                fence.arm(self.root, identifier)
        self.assertFalse(any(row[0] in {'stop', 'rm', 'exec'} for row in self.docker.calls))

    def test_contract_tampering_holds_before_stop(self):
        changes = [('Image', 'other'), ('RestartCount', 1), ('Name', '/atlas-dispatcharr')]
        for key, value in changes:
            with self.subTest(key=key):
                original = copy.deepcopy(self.docker.apps)
                self.docker.apps['1'*64][key] = value
                with self.assertRaises(fence.LifecycleError): self.arm()
                self.docker.apps = original
        cases = [('User', '1000:1000'), ('Cmd', ['foreign'])]
        for key, value in cases:
            with self.subTest(key=key):
                original = copy.deepcopy(self.docker.apps)
                self.docker.apps['1'*64]['Config'][key] = value
                with self.assertRaises(fence.LifecycleError): self.arm()
                self.docker.apps = original
        self.assertFalse(any(row[0] in {'stop', 'rm', 'exec'} for row in self.docker.calls))

    def test_host_and_mount_contract_changes_hold(self):
        cases = [('NetworkMode', 'host'), ('Privileged', True), ('AutoRemove', True),
            ('PidMode', 'host'), ('IpcMode', 'host'), ('UsernsMode', 'host'),
            ('Binds', ['/production:/data']), ('VolumesFrom', ['production']),
            ('RestartPolicy', {'Name': 'always'}), ('PortBindings', {'80/tcp': [{}]})]
        for key, value in cases:
            with self.subTest(key=key):
                original = copy.deepcopy(self.docker.apps)
                self.docker.apps['1'*64]['HostConfig'][key] = value
                with self.assertRaises(fence.LifecycleError): self.arm()
                self.docker.apps = original
        for change in ('readonly', 'bind', 'extra'):
            with self.subTest(mount=change):
                original = copy.deepcopy(self.docker.apps)
                mounts = self.docker.apps['1'*64]['Mounts']
                if change == 'readonly': mounts[0]['RW'] = False
                elif change == 'bind': mounts[0]['Type'] = 'bind'
                else: mounts.append(copy.deepcopy(mounts[0]))
                with self.assertRaises(fence.LifecycleError): self.arm()
                self.docker.apps = original
        self.assertFalse(any(row[0] in {'stop', 'rm', 'exec'} for row in self.docker.calls))

    def test_volume_options_or_label_changes_hold(self):
        data = fence.names(self.docker.identifier, 'teamarr')[1]
        for key, value in [('Options', {'device': '/production'}), ('Driver', 'other'),
                ('Labels', {}), ('Scope', 'global')]:
            with self.subTest(key=key):
                original = copy.deepcopy(self.docker.volumes)
                self.docker.volumes[data][key] = value
                with self.assertRaises(fence.LifecycleError): self.arm()
                self.docker.volumes = original
        self.assertFalse(any(row[0] in {'stop', 'rm', 'exec'} for row in self.docker.calls))

    def test_foreign_volume_reference_blocks_arm_and_recovery(self):
        self.docker.extra.add('f'*64)
        with self.assertRaises(fence.LifecycleError): self.arm()
        self.docker.extra.clear(); self.arm(); fence.detach(self.root)
        self.docker.extra.add('f'*64)
        with patch.object(fence.consumption, 'recover') as recover:
            with self.assertRaises(fence.LifecycleError): fence.recover(self.root)
            recover.assert_not_called()

    def test_restart_or_epoch_change_holds(self):
        self.arm(); self.docker.apps['2'*64]['State']['StartedAt'] = 'new-start'
        with self.assertRaises(fence.LifecycleError): fence.detach(self.root)
        self.assertFalse(any(row[0] in {'stop', 'rm', 'exec'} for row in self.docker.calls))

    def test_unclean_or_killed_exit_holds(self):
        self.arm(); self.docker.pg = 'in crash recovery'
        with self.assertRaises(fence.LifecycleError): fence.detach(self.root)
        self.docker.pg = 'in production'
        original = self.docker.command
        def killed(*args, **kwargs):
            value = original(*args, **kwargs)
            if args[0] == 'stop': self.docker.apps[args[-1]]['State']['ExitCode'] = 137
            return value
        with patch.object(fence, 'command', killed), self.assertRaises(fence.LifecycleError): fence.detach(self.root)
        self.assertFalse(any(row[0] == 'rm' for row in self.docker.calls))

    def test_missing_container_before_detaching_is_held(self):
        self.arm(); del self.docker.apps['2'*64]
        with self.assertRaises(fence.LifecycleError): fence.detach(self.root)

    def test_daemon_failure_is_not_absence(self):
        self.arm(); fence.detach(self.root); self.docker.available = False
        with patch.object(fence.consumption, 'recover') as recover:
            with self.assertRaises(fence.LifecycleError): fence.recover(self.root)
            recover.assert_not_called()

    def test_replacement_name_after_detach_is_held(self):
        self.arm(); saved = copy.deepcopy(self.docker.apps['1'*64]); fence.detach(self.root)
        saved['Id'] = 'f'*64; self.docker.apps['f'*64] = saved
        with self.assertRaises(fence.LifecycleError): fence.recover(self.root)

    def test_journal_binding_and_ledger_mode_are_checked(self):
        self.arm(); fence.detach(self.root)
        path = self.root/'DOCKER_LIFECYCLE.json'; raw = path.read_bytes()
        value = json.loads(raw); value['binding']['exposure'] = 'f'*64; fence.pub.write_json(path, value)
        with self.assertRaises(fence.LifecycleError): fence.recover(self.root)
        path.write_bytes(raw); path.chmod(0o644)
        with self.assertRaises(ValueError): fence.recover(self.root)

    def test_durable_transition_interruptions_resume(self):
        # Each intent is persisted before the next destructive Docker action.
        for boundary in (*fence.STAGES, 'removed:dispatcharr', 'removed:teamarr'):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.', dir='/tmp') as temp:
                root = Path(temp); original = fixture.fixture(root); fence.consumption.arm(root); fixture.mutate(root)
                docker = Docker()
                def die(name):
                    if name == boundary: raise InterruptedError(boundary)
                with patch.object(fence, 'command', docker.command):
                    with patch.object(fence, 'checkpoint', die):
                        with self.assertRaises(InterruptedError):
                            fence.arm(root, docker.identifier); fence.detach(root)
                    fence.detach(root); fence.recover(root); fixture.verify(root, original)


if __name__ == '__main__': unittest.main()
