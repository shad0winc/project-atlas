"""Guard the AIO fixture lifecycle without Docker or production state access."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


driver = load('cold_copy_driver', ROOT / 'scripts/diagnostics/sports-cold-copy-drill.py')
helper = load('cold_copy_helper', ROOT / 'scripts/lib/sports-cold-copy-drill.py')
adapter = load('cold_copy_adapter', ROOT / 'scripts/lib/sports-postgres-prepare.py')


class ColdCopyDrillTests(unittest.TestCase):
    def test_app_uses_pinned_image_owned_volume_no_production_environment_or_network(self):
        args = driver.app_arguments('app-owned', 'volume-owned', 'identifier')
        self.assertEqual(args[:2], ['docker', 'create'])
        self.assertEqual(args[-1], driver.IMAGE)
        self.assertIn('--network=none', args)
        self.assertIn('--log-driver=none', args)
        self.assertIn('--restart=no', args)
        self.assertIn('--pull=never', args)
        self.assertIn('type=volume,source=volume-owned,destination=/data,volume-nocopy', args)
        for forbidden in ('--env-file', '--privileged', '--publish', '--network=host', '--volumes-from'):
            self.assertNotIn(forbidden, args)
        self.assertFalse(any('type=bind' in value or '/mnt/' in value for value in args))
        environments = [args[index + 1] for index, value in enumerate(args) if value == '--env']
        self.assertEqual(set(environments), {'PUID=1000', 'PGID=1000', 'DISPATCHARR_ENV=aio',
            'POSTGRES_USER=dispatch', 'POSTGRES_DB=atlas_cold_drill',
            'POSTGRES_PASSWORD=atlas-isolated-drill-only', 'UWSGI_NICE_LEVEL=0', 'CELERY_NICE_LEVEL=0'})

    def test_helper_is_nonroot_readonly_volume_and_has_no_app_startup(self):
        args = driver.helper_arguments('helper-owned', 'volume-owned', 'identifier', 'bootstrap')
        for value in ('--read-only', '--user=1000:1000', '--cap-drop=ALL', '--network=none'):
            self.assertIn(value, args)
        self.assertIn('type=volume,source=volume-owned,destination=/source,readonly,volume-nocopy', args)
        self.assertEqual(args[args.index('--entrypoint') + 1], 'python3')
        self.assertNotIn('--cap-add=CHOWN', args)

    def item(self):
        return {'Image': driver.IMAGE, 'Config': {'Labels': {driver.LABEL: 'id'}},
            'HostConfig': {'NetworkMode': 'none', 'Privileged': False, 'PortBindings': {}, 'ReadonlyRootfs': True},
            'Mounts': [{'Type': 'volume', 'Name': 'vol', 'Destination': '/source', 'RW': False}]}

    def test_mount_attestation_rejects_bind_wrong_volume_writable_or_extra_mount(self):
        for change in ('bind', 'wrong-volume', 'writable', 'extra', 'ports', 'privileged', 'network', 'label'):
            item = self.item()
            if change == 'bind': item['Mounts'][0]['Type'] = 'bind'
            if change == 'wrong-volume': item['Mounts'][0]['Name'] = 'other'
            if change == 'writable': item['Mounts'][0]['RW'] = True
            if change == 'extra': item['Mounts'].append(dict(item['Mounts'][0]))
            if change == 'ports': item['HostConfig']['PortBindings'] = {'80/tcp': [{}]}
            if change == 'privileged': item['HostConfig']['Privileged'] = True
            if change == 'network': item['HostConfig']['NetworkMode'] = 'host'
            if change == 'label': item['Config']['Labels'][driver.LABEL] = 'other'
            with self.subTest(change=change), patch.object(driver, 'inspect', return_value=item):
                with self.assertRaises(RuntimeError): driver.owned_container('helper', 'id', 'vol', '/source', True)
        with patch.object(driver, 'inspect', return_value=self.item()):
            driver.owned_container('helper', 'id', 'vol', '/source', True)

    def test_cleanup_refuses_unowned_container_before_removal(self):
        item = self.item(); item['Config']['Labels'][driver.LABEL] = 'someone-else'
        result = subprocess.CompletedProcess([], 0, json.dumps([item]).encode(), b'')
        with patch.object(driver, 'invoke', return_value=result), patch.object(driver, 'docker') as docker:
            with self.assertRaises(RuntimeError): driver.cleanup(('app',), 'vol', 'id')
            docker.assert_not_called()

    def test_cleanup_checks_volume_label_driver_and_options(self):
        for volume in ({'Labels': {driver.LABEL: 'other'}, 'Driver': 'local', 'Options': None},
                       {'Labels': {driver.LABEL: 'id'}, 'Driver': 'nfs', 'Options': None},
                       {'Labels': {driver.LABEL: 'id'}, 'Driver': 'local', 'Options': {'device': '/mnt/storage'}}):
            result = subprocess.CompletedProcess([], 0, json.dumps([volume]).encode(), b'')
            with self.subTest(volume=volume), patch.object(driver, 'invoke', return_value=result), patch.object(driver, 'docker') as docker:
                with self.assertRaises(RuntimeError): driver.cleanup((), 'vol', 'id')
                docker.assert_not_called()

    def test_cleanup_absence_checks_daemon_and_never_lists_or_prunes_resources(self):
        result = subprocess.CompletedProcess([], 1, b'', b'not found')
        with patch.object(driver, 'invoke', return_value=result), patch.object(driver, 'docker') as docker:
            driver.cleanup(('app', 'helper'), 'vol', 'id')
            self.assertEqual(docker.call_count, 3)
            self.assertTrue(all(call.args == ('info', '--format', '{{.ServerVersion}}') for call in docker.call_args_list))

    def test_cleanup_removes_only_supplied_labelled_resources_in_reverse_order(self):
        container = subprocess.CompletedProcess([], 0, json.dumps([self.item()]).encode(), b'')
        volume = subprocess.CompletedProcess([], 0, json.dumps([{'Labels': {driver.LABEL: 'id'}, 'Driver': 'local', 'Options': None}]).encode(), b'')
        with patch.object(driver, 'invoke', side_effect=[container, container, volume]), patch.object(driver, 'docker') as docker:
            driver.cleanup(('app', 'helper'), 'vol', 'id')
            self.assertEqual([call.args for call in docker.call_args_list], [
                ('rm', '--force', '--volumes', 'helper'), ('rm', '--force', '--volumes', 'app'),
                ('volume', 'rm', 'vol')])

    def test_subprocess_failures_are_sanitized_and_output_is_bounded(self):
        result = subprocess.CompletedProcess([], 1, b'', b'private-error')
        with patch.object(driver.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(RuntimeError, '^Isolated cold-copy drill contract failed$'):
                driver.invoke('fixture')
        result = subprocess.CompletedProcess([], 0, b'x' * 1048577, b'')
        with patch.object(driver.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError): driver.invoke('fixture')

    def test_helper_requires_exact_identity_and_explicit_scope_before_source_access(self):
        for uid, gid, flag in ((0, 0, '1'), (1000, 999, '1'), (1000, 1000, '0')):
            with self.subTest(uid=uid, gid=gid), patch.object(helper.os, 'geteuid', return_value=uid), patch.object(helper.os, 'getegid', return_value=gid), patch.dict(os.environ, {'ATLAS_COLD_COPY_DRILL': flag}), patch.object(adapter, 'directory') as directory:
                with self.assertRaises(adapter.PrepareError): helper.run(adapter)
                directory.assert_not_called()

    def test_helper_rejects_dirty_source_without_copying_or_starting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(helper.os, 'geteuid', return_value=1000), patch.object(helper.os, 'getegid', return_value=1000), patch.dict(os.environ, {'ATLAS_COLD_COPY_DRILL': '1'}), patch.object(adapter, 'directory', return_value=root), patch.object(adapter, 'tools_for', return_value=('17', {'psql': Path('/fixed/psql')})), patch.object(adapter, 'cold_state', side_effect=adapter.PrepareError('cluster-not-cleanly-stopped')), patch.object(adapter, 'copy_cluster') as copy:
                with self.assertRaises(adapter.PrepareError): helper.run(adapter)
                copy.assert_not_called()

    def test_helper_does_not_forward_arbitrary_failure_text(self):
        output = io.StringIO()
        with patch.object(helper, 'run', side_effect=RuntimeError('synthetic-private-detail')), contextlib.redirect_stderr(output):
            self.assertEqual(helper.main(adapter), 1)
        self.assertEqual(output.getvalue(), 'COLD_COPY_HELPER=FAIL category=helper-failed\n')

    def test_source_hash_pins_match_adapter_and_helper(self):
        source = (ROOT / 'scripts/diagnostics/sports-cold-copy-drill.py').read_text()
        for path in (ROOT / 'scripts/lib/sports-postgres-prepare.py', ROOT / 'scripts/lib/sports-cold-copy-drill.py'):
            self.assertGreaterEqual(source.count(hashlib.sha256(path.read_bytes()).hexdigest()), 2)

    def test_clean_state_failures_identify_stage_without_accepting_dirty_source(self):
        for stage in ('initial-source', 'final-clone', 'final-source'):
            with self.subTest(stage=stage), patch.object(adapter, 'cold_state', side_effect=adapter.PrepareError('cluster-not-cleanly-stopped')):
                with self.assertRaisesRegex(adapter.PrepareError, '^' + stage + '-cluster-not-cleanly-stopped$'):
                    helper.checked_cold(adapter, Path('/fixed/cluster'), {}, {}, stage)

    def test_lifecycle_stops_owned_app_before_creating_readonly_helper_and_always_cleans(self):
        pointer = Mock()
        pointer.is_file.return_value = True; pointer.is_symlink.return_value = False
        pointer.read_bytes.return_value = (driver.DEPLOYMENT + '\n').encode()
        events = []
        items = {}
        fail_stop = [False]
        def command(*args, **kwargs):
            if args[0] == 'git': return subprocess.CompletedProcess(args, 0, (driver.HEAD + '\n').encode(), b'')
            if args[:2] == ('docker', 'create'):
                name = args[args.index('--name') + 1]
                volume = next(a for a in args if a.startswith('type=volume,')).split('source=')[1].split(',')[0]
                label = args[args.index('--label') + 1].split('=', 1)[1]
                readonly = '--read-only' in args
                item = self.item(); item['Config']['Labels'][driver.LABEL] = label
                item['HostConfig']['ReadonlyRootfs'] = readonly
                item['Mounts'][0].update(Name=volume, Destination='/source' if readonly else '/data', RW=not readonly)
                item['State'] = {'Running': False, 'Status': 'created', 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}
                items[name] = item; events.append('helper-create' if readonly else 'app-create')
                return subprocess.CompletedProcess(args, 0, b'fixture-id\n', b'')
            if args[:2] == ('docker', 'exec'):
                events.append('ready'); return subprocess.CompletedProcess(args, 0, b'ready\n', b'')
            if args[:4] == ('docker', 'start', '--attach', '--interactive'):
                events.append('helper-run')
                items[args[-1]]['State']['Status'] = 'exited'
                return subprocess.CompletedProcess(args, 0, json.dumps(driver.EXPECTED).encode(), b'')
            raise AssertionError('Unexpected subprocess invocation')
        def docker(*args, **kwargs):
            if args[:2] == ('image', 'inspect'):
                return json.dumps([{'Id': driver.IMAGE, 'Config': {'Entrypoint': ['/app/docker/entrypoint.sh'], 'Cmd': None, 'Volumes': None}}])
            if args[:2] == ('volume', 'create'): return args[-1]
            if args[0] == 'start':
                items[args[1]]['State'].update(Running=True, Status='running', Pid=123)
                return args[1]
            if args[0] == 'exec':
                if args[-1] == 'stop':
                    self.assertEqual(args[1:4], ('--user', '1000:1000', next(iter(items))))
                    self.assertEqual(args[4:], ('/usr/lib/postgresql/17/bin/pg_ctl', '-D', '/data/db', '-m', 'fast', '-w', '-t', '20', 'stop'))
                    events.append('postgres-fast-stop')
                    if fail_stop[0]: raise RuntimeError('fixture native stop failure')
                    return ''
                events.append('snapshot'); return 'snapshot-captured'
            if args[0] == 'stop':
                events.append('app-stop'); items[args[-1]]['State'].update(Running=False, Status='exited', Pid=0)
                return args[-1]
            raise AssertionError('Unexpected Docker invocation')
        path_factory = lambda value: pointer if str(value) == '/mnt/storage/configs/atlas/deployments/current' else Path(value)
        with patch.object(driver, 'Path', side_effect=path_factory), patch.object(driver, 'invoke', side_effect=command), patch.object(driver, 'docker', side_effect=docker), patch.object(driver, 'inspect', side_effect=lambda name: items[name]), patch.object(driver, 'observation', return_value=['unchanged']), patch.object(driver, 'cleanup') as cleanup, contextlib.redirect_stdout(io.StringIO()):
            driver.run()
            self.assertEqual(events, ['app-create', 'ready', 'snapshot', 'postgres-fast-stop', 'app-stop', 'helper-create', 'helper-run'])
            cleanup.assert_called_once()
            events.clear(); items.clear(); cleanup.reset_mock(); fail_stop[0] = True
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(RuntimeError): driver.run()
            self.assertEqual(events, ['app-create', 'ready', 'snapshot', 'postgres-fast-stop'])
            cleanup.assert_called_once()


if __name__ == '__main__': unittest.main()
