"""Live verifier guards source files, startup, authority ownership and drift."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest.mock import patch

from tests.core import test_deployment_mixed_runtime as legacy
from tests.core import test_ingress_provenance_extension as foundation

M = legacy.M
E = M.extension_module()


class ImmutableSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'atlas').mkdir()
        (self.source / 'atlas/main.py').write_bytes(b'pass\n')
        (self.source / 'run').write_bytes(b'#!/bin/sh\n')
        self.archived = {
            'atlas/main.py': {'sha256': hashlib.sha256(b'pass\n').hexdigest(), 'executable': False},
            'run': {'sha256': hashlib.sha256(b'#!/bin/sh\n').hexdigest(), 'executable': True}}
        (self.source / 'atlas/main.py').chmod(0o444)
        (self.source / 'run').chmod(0o555)
        (self.source / 'atlas').chmod(0o555)
        self.source.chmod(0o555)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for parent, dirs, files in os.walk(self.root):
            if not Path(parent).is_symlink(): Path(parent).chmod(0o700)
            for name in dirs:
                path = Path(parent) / name
                if not path.is_symlink(): path.chmod(0o700)
        self.temp.cleanup()

    def verify(self):
        E.verify_source(self.source, self.archived, owner_uid=os.getuid(), owner_gid=os.getgid())

    def test_real_directory_and_streamed_source_pass(self):
        self.verify()

    def test_large_binary_has_no_old_helper_size_limit(self):
        self.source.chmod(0o755)
        raw = b'x' * (2 * 1024 * 1024)
        (self.source / 'maintenance.png').write_bytes(raw)
        (self.source / 'maintenance.png').chmod(0o444)
        self.source.chmod(0o555)
        self.archived['maintenance.png'] = {'sha256': hashlib.sha256(raw).hexdigest(), 'executable': False}
        self.verify()

    def test_writable_source_file_refuses(self):
        (self.source / 'atlas/main.py').chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'file metadata'):
            self.verify()

    def test_writable_source_directory_refuses(self):
        (self.source / 'atlas').chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'directory metadata'):
            self.verify()

    def test_wrong_source_owner_refuses(self):
        with self.assertRaisesRegex(ValueError, 'directory metadata'):
            E.verify_source(self.source, self.archived, owner_uid=os.getuid() + 1, owner_gid=os.getgid())

    def test_corrupt_readonly_bytes_refuse(self):
        path = self.source / 'atlas/main.py'
        path.chmod(0o644)
        path.write_bytes(b'evil\n')
        path.chmod(0o444)
        with self.assertRaisesRegex(ValueError, 'bytes or identity'):
            self.verify()

    def test_untracked_source_file_refuses(self):
        self.source.chmod(0o755)
        (self.source / 'extra.py').write_bytes(b'pass\n')
        (self.source / 'extra.py').chmod(0o444)
        self.source.chmod(0o555)
        with self.assertRaises(ValueError):
            self.verify()

    def test_missing_source_file_refuses(self):
        (self.source / 'atlas').chmod(0o755)
        (self.source / 'atlas/main.py').unlink()
        (self.source / 'atlas').chmod(0o555)
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.verify()

    def test_hardlink_refuses(self):
        os.link(self.source / 'atlas/main.py', self.root / 'alias')
        with self.assertRaisesRegex(ValueError, 'file or link'):
            self.verify()

    def test_root_or_ancestor_symlink_refuses(self):
        link = self.root / 'alias'
        link.symlink_to(self.source, target_is_directory=True)
        for path in (link, link / 'atlas'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                E.verify_source(path, self.archived, owner_uid=os.getuid(), owner_gid=os.getgid())

    def test_child_symlink_refuses(self):
        (self.source / 'atlas').chmod(0o755)
        (self.source / 'atlas/main.py').unlink()
        (self.source / 'atlas/main.py').symlink_to(self.source / 'run')
        (self.source / 'atlas').chmod(0o555)
        with self.assertRaises(ValueError):
            self.verify()

    def test_writable_parent_refuses(self):
        self.root.chmod(0o777)
        with self.assertRaisesRegex(ValueError, 'parent is writable'):
            self.verify()


class LiveChecksTests(unittest.TestCase):
    def setUp(self):
        self.fixture = foundation.IngressExtensionTests('test_valid_extension_keeps_base_ledger_and_sports_evidence')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.record, self.ext = self.fixture.record, self.fixture.ext
        self.fixture.files['apps/api/atlas_api/services/maintenance_access.py'] = b'pass\n'
        self.rows = {}
        self.images = {}
        for index, role in enumerate(('api', 'portal', 'caddy'), 1):
            config = {'User': {'api': 'atlas', 'portal': 'nextjs', 'caddy': ''}[role],
                      'Cmd': ['fixture-' + role], 'Entrypoint': None, 'WorkingDir': '/srv' if role == 'api' else '/app',
                      'Env': ['PYTHONPATH=/srv:/srv/apps/api', 'ATLAS_MAINTENANCE_CONTROL_SOCKET=' + self.ext['authority']['socket']] if role == 'api' else []}
            image_id = self.ext['images'][role]['image_id'] if role != 'caddy' else self.ext['caddy']['image_id']
            labels = {'org.opencontainers.image.revision': self.ext['released_commit'],
                      'io.project-atlas.archive-source-commit': self.ext['source_archive_commit'],
                      'io.project-atlas.source-tree': self.ext['source_tree']}
            if role != 'caddy':
                labels['io.project-atlas.build-recipe-sha256'] = M.digest(self.record / ('ingress-' + role + '-build.Dockerfile'))
            config['Labels'] = labels
            row = {'Id': str(index) * 64, 'Image': image_id, 'Name': '/atlas-' + role,
                   'Config': copy.deepcopy(config), 'HostConfig': {'Privileged': False, 'SecurityOpt': ['no-new-privileges:true'],
                   'ReadonlyRootfs': role == 'caddy', 'PidMode': '', 'IpcMode': ''}, 'RestartCount': 0,
                   'Mounts': [], 'State': {'Running': True, 'Pid': 100 + index, 'StartedAt': '2026-10-19T00:00:00Z',
                                         'Health': {'Status': 'healthy'}}}
            if role == 'api':
                row['Mounts'] = [{'Destination': '/run/atlas-maintenance-control', 'Source': '/run/atlas-maintenance-control',
                                  'Type': 'bind', 'RW': False}]
            if role == 'caddy':
                row['Mounts'] = [{'Destination': dest, 'Source': source, 'Type': 'bind', 'RW': False} for dest, source in (
                    ('/etc/caddy', self.ext['caddy']['immutable_source'] + '/infra/caddy'),
                    ('/srv', self.ext['caddy']['immutable_source'] + '/infra/caddy/site'),
                    ('/etc/atlas-maintenance', '/mnt/storage/configs/atlas/maintenance'))]
            self.rows['atlas-' + role] = row
            self.images[image_id] = {'Id': image_id, 'Config': config}
        self.archived = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'executable': False}
                         for name, raw in self.fixture.files.items()}
        self.context = types.SimpleNamespace(read=M.read, archive_files=lambda *args: self.archived,
                                             inspect=lambda name: copy.deepcopy(self.rows[name]))
        self.calls = []

    def query(self, args, **kwargs):
        self.calls.append(args)
        if args[:3] == ['docker', 'image', 'inspect']:
            return json.dumps([self.images[args[3]]]).encode()
        if args[:3] == ['docker', 'exec', '-i']:
            data = json.loads(kwargs['data'])
            self.assertIn('/srv/apps/api/atlas_api/services/maintenance_access.py', data)
            self.assertIn('-I', args)
            return b''
        if args[:3] == ['docker', 'exec', 'atlas-portal']:
            return b''
        self.fail('Unexpected runtime command: ' + repr(args))

    def live(self):
        with patch.object(E, 'verify_source') as source, patch.object(E, 'verify_authority', return_value={'MainPID': '123'}) as authority, \
             patch.object(E, 'query', side_effect=self.query):
            E.check_live(self.context, self.record)
            source.assert_called_once_with(self.ext['caddy']['immutable_source'], self.archived)
            self.assertEqual(authority.call_count, 2)

    def test_readonly_live_orchestration_covers_three_components_and_two_probes(self):
        self.live()
        self.assertEqual(len(self.calls), 5)
        self.assertTrue(all(args[:2] in (['docker', 'image'], ['docker', 'exec']) for args in self.calls))

    def test_healthy_component_state_is_required(self):
        self.rows['atlas-api']['State']['Health']['Status'] = 'starting'
        with self.assertRaisesRegex(ValueError, 'healthy and running'):
            self.live()

    def test_wrong_runtime_image_refuses(self):
        self.rows['atlas-api']['Image'] = 'sha256:' + '9' * 64
        with self.assertRaisesRegex(ValueError, 'image/name'):
            self.live()

    def test_wrong_image_source_labels_refuse(self):
        self.images[self.ext['images']['api']['image_id']]['Config']['Labels']['io.project-atlas.source-tree'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'source labels'):
            self.live()

    def test_startup_override_or_root_api_refuses(self):
        for field, value in (('Cmd', ['other']), ('User', 'root')):
            with self.subTest(field=field):
                old = self.rows['atlas-api']['Config'][field]
                self.rows['atlas-api']['Config'][field] = value
                with self.assertRaises(ValueError): self.live()
                self.rows['atlas-api']['Config'][field] = old

    def test_loader_environment_refuses(self):
        self.rows['atlas-portal']['Config']['Env'].append('NODE_OPTIONS=--require=/tmp/evil.js')
        with self.assertRaisesRegex(ValueError, 'executable environment'):
            self.live()

    def test_api_writable_socket_mount_refuses(self):
        self.rows['atlas-api']['Mounts'][0]['RW'] = True
        with self.assertRaises(ValueError): self.live()

    def test_api_source_or_control_mount_refuses(self):
        for target in ('/srv/atlas', '/var/run/docker.sock', '/mnt/storage/configs/atlas/deployments'):
            with self.subTest(target=target):
                self.rows['atlas-api']['Mounts'].append({'Destination': target, 'Source': target, 'Type': 'bind', 'RW': True})
                with self.assertRaises(ValueError): self.live()
                self.rows['atlas-api']['Mounts'].pop()

    def test_portal_mount_refuses(self):
        self.rows['atlas-portal']['Mounts'].append({'Destination': '/app', 'Source': '/private/source', 'Type': 'bind', 'RW': False})
        with self.assertRaises(ValueError): self.live()

    def test_caddy_wrong_or_nested_source_refuses(self):
        self.rows['atlas-caddy']['Mounts'][0]['Source'] = '/opt/project-atlas-v1-main/infra/caddy'
        with self.assertRaises(ValueError): self.live()

    def test_privileged_or_missing_nonewprivs_refuses(self):
        self.rows['atlas-api']['HostConfig']['Privileged'] = True
        with self.assertRaisesRegex(ValueError, 'execution boundary'):
            self.live()

    def test_runtime_restart_during_check_refuses(self):
        counts = {}
        def inspect(name):
            counts[name] = counts.get(name, 0) + 1
            row = copy.deepcopy(self.rows[name])
            if counts[name] > 1: row['State']['Pid'] += 1
            return row
        self.context.inspect = inspect
        with self.assertRaisesRegex(ValueError, 'runtime changed'):
            self.live()

    def test_authority_restart_between_checks_refuses(self):
        with patch.object(E, 'verify_source'), patch.object(E, 'verify_authority', side_effect=[{'MainPID': '1'}, {'MainPID': '2'}]), \
             patch.object(E, 'query', side_effect=self.query), self.assertRaisesRegex(ValueError, 'authority changed'):
            E.check_live(self.context, self.record)

    def test_native_live_dispatch_preserves_sports_checks(self):
        extension = M.extension_module()
        with patch.object(M, 'extension_module', return_value=extension), \
             patch.object(extension, 'check_live') as ingress, \
             patch.object(M, 'inspect', side_effect=self.fixture.fixture.inspect) as inspect, \
             patch.object(M.subprocess, 'run') as run:
            run.return_value.returncode = 0
            M.check_live(self.record)
            ingress.assert_called_once()
            self.assertEqual([item.args[0] for item in inspect.call_args_list],
                             ['atlas-sports-writer', 'atlas-sports-controller'])

    def test_sports_exclusion_does_not_skip_ingress_verification(self):
        extension = M.extension_module()
        with patch.object(M, 'extension_module', return_value=extension), \
             patch.object(extension, 'check_live') as ingress, \
             patch.object(M, 'inspect', side_effect=self.fixture.fixture.inspect) as inspect, \
             patch.object(M.subprocess, 'run') as run:
            run.return_value.returncode = 0
            M.check_live(self.record, 'sports')
            ingress.assert_called_once()
            self.assertEqual([item.args[0] for item in inspect.call_args_list], ['atlas-sports-writer'])

    def test_packaged_file_probe_failure_refuses(self):
        original = self.query
        def query(args, **kwargs):
            if args[:3] == ['docker', 'exec', '-i']:
                raise ValueError('copied bytes differ')
            return original(args, **kwargs)
        with patch.object(E, 'verify_source'), patch.object(E, 'verify_authority', return_value={}), \
             patch.object(E, 'query', side_effect=query), self.assertRaises(ValueError):
            E.check_live(self.context, self.record)


class AuthorityChecksTests(unittest.TestCase):
    def setUp(self):
        self.source = '/mnt/storage/configs/atlas/deployments/repairs/fixture/source'
        self.authority = {'unit_path': '/etc/systemd/system/atlas-maintenance-control.service'}
        self.properties = {'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'running',
                           'FragmentPath': self.authority['unit_path'], 'DropInPaths': '', 'NeedDaemonReload': 'no',
                           'WorkingDirectory': self.source, 'User': 'root', 'Group': '20000',
                           'MainPID': '123', 'NRestarts': '0', 'ExecMainStartTimestampMonotonic': '456'}

    def test_service_properties_pass(self):
        E.authority_properties(self.properties, self.source, self.authority)

    def test_dropin_inactive_stale_unit_or_wrong_process_refuse(self):
        for key, value in (('DropInPaths', '/private/override.conf'), ('NeedDaemonReload', 'yes'),
                           ('MainPID', '0'), ('Group', 'root'), ('ActiveState', 'inactive'), ('WorkingDirectory', '/old/source')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                E.authority_properties({**self.properties, key: value}, self.source, self.authority)

    def test_socket_metadata_pass(self):
        sock = types.SimpleNamespace(st_mode=stat.S_IFSOCK | 0o660, st_uid=0, st_gid=20000)
        parent = types.SimpleNamespace(st_mode=stat.S_IFDIR | 0o750, st_uid=0, st_gid=20000)
        E.socket_metadata(sock, parent)
        for changed in (stat.S_IFSOCK | 0o666, stat.S_IFLNK | 0o660):
            sock.st_mode = changed
            with self.assertRaises(ValueError): E.socket_metadata(sock, parent)

    def test_socket_listener_binds_the_unit_process(self):
        raw = b'Num RefCount Protocol Flags Type St Inode Path\n0000: 00000002 00000000 00010000 0001 01 12345 /run/atlas-maintenance-control/control.sock\n'
        E.socket_listener(raw, '/run/atlas-maintenance-control/control.sock', ['socket:[12345]'])
        with self.assertRaises(ValueError):
            E.socket_listener(raw, '/run/atlas-maintenance-control/control.sock', ['socket:[999]'])

    def test_capability_or_credentials_widening_refuses(self):
        raw = b'Uid:\t0\t0\t0\t0\nGid:\t20000\t20000\t20000\t20000\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\nCapBnd:\t0000000000000000\n'
        E.process_status(raw)
        for bad in (raw.replace(b'NoNewPrivs:\t1', b'NoNewPrivs:\t0'), raw.replace(b'CapEff:\t0000000000000000', b'CapEff:\t0000000000000001')):
            with self.assertRaises(ValueError): E.process_status(bad)

    def test_incomplete_or_duplicate_systemctl_properties_refuse(self):
        for raw in (b'MainPID=123\n', b'MainPID=123\nMainPID=456\n'):
            with patch.object(E, 'query', return_value=raw), self.assertRaises(ValueError):
                E.service_properties()


if __name__ == '__main__':
    unittest.main()


class AuthorityInspectionTests(unittest.TestCase):
    """Exercise the full inspector with filesystem/proc/systemd query boundaries supplied."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'atlas-maintenance-control.service').write_bytes(b'pinned-unit\n')
        (self.root / 'atlas-maintenance-control.service').chmod(0o644)
        self.source = '/mnt/storage/configs/atlas/deployments/repairs/fixture/source'
        self.sock = '/run/atlas-maintenance-control/control.sock'
        self.unit = '/etc/systemd/system/atlas-maintenance-control.service'
        self.ext = {'caddy': {'immutable_source': self.source}, 'authority': {'socket': self.sock, 'unit_path': self.unit}}
        self.properties = {'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'running',
                           'FragmentPath': self.unit, 'DropInPaths': '', 'NeedDaemonReload': 'no',
                           'WorkingDirectory': self.source, 'User': 'root', 'Group': '20000',
                           'MainPID': str(os.getpid()), 'NRestarts': '0', 'ExecMainStartTimestampMonotonic': '456'}
        self.command = ['/usr/bin/python3', '-P', '-B', '-m', 'atlas.maintenance_control_server',
                        '--runtime-root', '/mnt/storage/configs/atlas', '--socket', self.sock,
                        '--allowed-uid', '999', '--socket-gid', '20000']
        self.status = b'Uid:\t0\t0\t0\t0\nGid:\t20000\t20000\t20000\t20000\nNoNewPrivs:\t1\nCapEff:\t0000000000000000\nCapBnd:\t0000000000000000\n'
        self.unit_bytes = b'pinned-unit\n'
        self.start_ticks = b'99'

    def read(self, path):
        path = Path(path)
        if path.name == 'maintenance-authority.service': return self.unit_bytes
        if path.name == 'stat': return b'123 (python3) S ' + b'0 ' * 18 + self.start_ticks + b' 0\n'
        if path.name == 'status': return self.status
        if path.name == 'cmdline': return b'\0'.join(part.encode() for part in self.command) + b'\0'
        if path.name == 'environ': return b'PYTHONPATH=' + self.source.encode() + b'\0PYTHONDONTWRITEBYTECODE=1\0'
        if str(path) == '/proc/net/unix':
            return b'Num RefCount Protocol Flags Type St Inode Path\n0000: 00000002 00000000 00010000 0001 01 12345 ' + self.sock.encode() + b'\n'
        raise AssertionError('Unexpected read')

    def inspect(self, *, properties=None):
        original_stat, original_fstat, original_readlink = os.stat, os.fstat, os.readlink
        python = str(Path('/usr/bin/python3').resolve(strict=True))
        def directory(path): return os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        def fstat(fd):
            info = original_fstat(fd)
            if stat.S_ISREG(info.st_mode):
                return types.SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0, st_gid=0, st_nlink=1)
            return types.SimpleNamespace(st_mode=stat.S_IFDIR | 0o750, st_uid=0, st_gid=20000)
        def lstat(path, *args, **kwargs):
            if path == 'control.sock':
                return types.SimpleNamespace(st_mode=stat.S_IFSOCK | 0o660, st_uid=0, st_gid=20000,
                                             st_dev=1, st_ino=2, st_ctime_ns=3)
            return original_stat(path, *args, **kwargs)
        def link(path):
            if not str(path).startswith('/proc/'): return original_readlink(path)
            if Path(path).name == 'cwd': return self.source
            if Path(path).name == 'exe': return python
            return 'socket:[12345]'
        with patch.object(E, 'open_directory', side_effect=directory), patch.object(E.os, 'fstat', side_effect=fstat), \
             patch.object(E.os, 'stat', side_effect=lstat), patch.object(E.os, 'readlink', side_effect=link), \
             patch.object(E, 'service_properties', side_effect=properties or [self.properties, self.properties]):
            return E.verify_authority(types.SimpleNamespace(read=self.read), self.root, self.ext)

    def test_complete_authority_inspection_passes(self):
        self.assertEqual(self.inspect(), self.properties)

    def test_changed_installed_unit_refuses(self):
        self.unit_bytes = b'other-unit\n'
        with self.assertRaisesRegex(ValueError, 'unit bytes'):
            self.inspect()

    def test_process_command_override_refuses(self):
        self.command.remove('-P')
        with self.assertRaisesRegex(ValueError, 'command/source'):
            self.inspect()

    def test_service_restart_during_inspection_refuses(self):
        with self.assertRaisesRegex(ValueError, 'process or service changed'):
            self.inspect(properties=[self.properties, {**self.properties, 'NRestarts': '1'}])
