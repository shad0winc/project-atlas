"""Signal, subscriber progress and refusal tests; real Docker acceptance runs on CT100."""
import copy
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

support = load('four_service_test', 'scripts/lib/sports-four-service-lifecycle.py')
native = load('four_service_native_test', 'scripts/lib/sports-native-consumption.py')


def wait_for(predicate, process, timeout=8):
    deadline = time.monotonic()+timeout
    while not predicate():
        if process.poll() is not None: raise AssertionError('Fixture exited before readiness')
        if time.monotonic() >= deadline: raise AssertionError('Fixture readiness deadline')
        time.sleep(.02)


def cleanup(process):
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)


class RuntimeGuards(unittest.TestCase):
    def row(self, role, root, job):
        name = 'atlas-four-service-'+role+'-'+job
        mounts, env = support.contract(role, root)
        groups = ['20000', '20001'] if role == 'api' else ['20000'] if role != 'sports-writer' else None
        row = {'Id': 'a'*64, 'Name': '/'+name, 'Image': support.IMAGES[role],
            'Config': {'Labels': {support.LABEL: job}, 'Entrypoint': None, 'Cmd': support.COMMANDS[role],
                'User': '999:999' if role == 'api' else '1000:1000', 'WorkingDir': support.WORKDIRS[role],
                'Env': [key+'='+value for key, value in env.items()], 'Volumes': None,
                'Healthcheck': {'Test': ['NONE']}},
            'HostConfig': {'ReadonlyRootfs': True, 'Privileged': False, 'NetworkMode': 'none', 'PidMode': '',
                'IpcMode': 'private', 'CapAdd': None, 'CapDrop': ['ALL'], 'GroupAdd': groups,
                'SecurityOpt': ['no-new-privileges:true'], 'PortBindings': {}, 'RestartPolicy': {'Name': 'no'},
                'LogConfig': {'Type': 'none'}, 'Memory': 256*1024*1024, 'NanoCpus': 500000000,
                'PidsLimit': 96, 'Tmpfs': {'/tmp': 'rw,noexec,nosuid,size=16777216,mode=1777'}, 'Devices': [], 'VolumesFrom': None, 'Links': None},
            'NetworkSettings': {'Ports': {'8000/tcp': None} if role == 'api' else {}},
            'Mounts': [{'Type': 'bind', 'Source': src, 'Destination': dest, 'RW': rw, 'Propagation': 'rprivate'}
                for src, dest, rw in mounts]}
        return name, row

    def test_all_default_commands_and_private_mounts_match_numeric_identity(self):
        job = 'b'*32; root = Path('/tmp/atlas-four-service.guard')
        for role in support.ROLES:
            name, row = self.row(role, root, job)
            support.inspect_owned(row, role, name, job, root, 'a'*64)
            row['Mounts'].reverse(); support.inspect_owned(row, role, name, job, root, 'a'*64)
            args = support.arguments(role, name, job, root)
            self.assertEqual(args[-1], support.IMAGES[role]); self.assertIn('--pull=never', args)
            self.assertNotIn('--entrypoint', args); self.assertIn('--network=none', args)

    def test_refuse_host_network_wrong_command_uid_environment_or_production_mount(self):
        job = 'b'*32; root = Path('/tmp/atlas-four-service.guard')
        for role in support.ROLES:
            name, row = self.row(role, root, job)
            for section, key, value in [('Config', 'User', '0:0'), ('Config', 'Cmd', ['sh']),
                    ('Config', 'Env', []), ('HostConfig', 'NetworkMode', 'host'),
                    ('HostConfig', 'ReadonlyRootfs', False), ('HostConfig', 'GroupAdd', ['0']),
                    ('HostConfig', 'PortBindings', {'8000/tcp': [{'HostPort': '8000'}]})]:
                changed = copy.deepcopy(row); changed[section][key] = value
                with self.subTest(role=role, key=key), self.assertRaises(ValueError):
                    support.inspect_owned(changed, role, name, job, root, 'a'*64)
            changed = copy.deepcopy(row); changed['Mounts'][0]['Source'] = '/mnt/storage/configs/atlas'
            with self.assertRaises(ValueError): support.inspect_owned(changed, role, name, job, root, 'a'*64)
            changed = copy.deepcopy(row); changed['Mounts'].append(changed['Mounts'][0])
            with self.assertRaises(ValueError): support.inspect_owned(changed, role, name, job, root, 'a'*64)

    def test_failure_location_does_not_print_exception_messages(self):
        from unittest.mock import patch
        output = io.StringIO()
        with patch.object(support, '_capture', side_effect=RuntimeError('synthetic-secret-must-not-print')):
            with contextlib.redirect_stdout(output), self.assertRaises(RuntimeError):
                support.capture(None, None, None)
        self.assertIn('ACTUAL_FOUR_SERVICE_FAILURE=', output.getvalue())
        self.assertNotIn('synthetic-secret', output.getvalue())

    def test_source_staging_retains_operator_owner_executable_processor_and_fixture_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); support.stage(native, root)
            for path in (root/'source').rglob('*'):
                self.assertEqual((path.stat().st_uid, path.stat().st_gid), (os.geteuid(), os.getegid()))
            processor = root/'source/modules/notifications/src/processor.py'
            self.assertEqual(processor.stat().st_mode & 0o777, 0o755)
            self.assertEqual((root/'source/config/atlas.conf').read_text(), support.CONFIG)
            self.assertFalse(list((root/'source').rglob('.env')))

    def test_snapshot_rejects_symlinks_and_records_changed_bytes_modes_and_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); file = root/'private'; file.write_bytes(b'one')
            before = support.tree(root); file.write_bytes(b'two')
            self.assertNotEqual(before, support.tree(root))
            (root/'link').symlink_to(file)
            with self.assertRaises(ValueError): support.tree(root)


class ActualWorkerSignals(unittest.TestCase):
    def test_controller_once_keeps_cycle_result_and_restores_handlers(self):
        sys.path.insert(0, str(ROOT/'modules/sports/src'))
        sys.path.insert(0, str(ROOT))
        try:
            worker = load('four_service_once_test', 'modules/sports/src/worker.py')
            from unittest.mock import patch
            before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            with patch.object(worker, 'run_cycle', return_value=7) as cycle, patch.object(sys, 'argv', ['worker.py', '--once']):
                self.assertEqual(worker.main(), 7)
                cycle.assert_called_once_with()
            self.assertEqual(before, {sig: signal.getsignal(sig) for sig in before})
        finally:
            sys.path.pop(0); sys.path.pop(0)

    def test_controller_sigterm_interrupts_long_idle_interval_without_another_cycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); heartbeat = root/'heartbeat'
            env = {'PATH': os.environ['PATH'], 'PYTHONDONTWRITEBYTECODE': '1',
                'PYTHONPATH': str(ROOT)+':'+str(ROOT/'modules/sports/src'),
                'SPORTS_THESPORTSDB_API_KEY': '', 'SPORTS_CONTROLLER_INTERVAL_SECONDS': '60',
                'SPORTS_CONTROLLER_HEARTBEAT_FILE': str(heartbeat)}
            process = subprocess.Popen([sys.executable, '-B', str(ROOT/'modules/sports/src/worker.py')],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                wait_for(heartbeat.exists, process)
                before = heartbeat.read_bytes(); process.send_signal(signal.SIGTERM)
                self.assertEqual(process.wait(timeout=3), 0)
                self.assertEqual(heartbeat.read_bytes(), before)
            finally: cleanup(process)

    def test_controller_stop_during_cycle_finishes_it_without_starting_next(self):
        # Run the real main with only run_cycle injected to block in a controlled
        # local test. Actual default-command/no-provider Docker coverage is separate.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bootstrap = """import importlib.util,os,signal,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('signal_worker',os.environ['WORKER'])
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
root=Path(os.environ['FIXTURE'])
def cycle():
 with (root/'cycles').open('a') as stream:stream.write('cycle\\n')
 (root/'ready').touch()
 while not (root/'release').exists():time.sleep(.01)
 (root/'finished').touch()
 return 0
w.run_cycle=cycle
raise SystemExit(w.main())
"""
            env = dict(os.environ, WORKER=str(ROOT/'modules/sports/src/worker.py'), FIXTURE=str(root),
                PYTHONPATH=str(ROOT)+':'+str(ROOT/'modules/sports/src'), PYTHONDONTWRITEBYTECODE='1')
            process = subprocess.Popen([sys.executable, '-B', '-c', bootstrap], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                wait_for((root/'ready').exists, process); process.send_signal(signal.SIGTERM)
                time.sleep(.05); (root/'release').touch()
                self.assertEqual(process.wait(timeout=3), 0)
                self.assertTrue((root/'finished').exists())
                self.assertEqual((root/'cycles').read_text(), 'cycle\n')
            finally: cleanup(process)

    def test_notifications_actual_processor_cursor_restart_and_prompt_idle_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); support.stage(native, root)
            source = root/'source'; state = root/'notifications'; state.mkdir()
            runtime = root/'runtime'; subscribers = runtime/'subscribers'; subscribers.mkdir(parents=True)
            events = runtime/'events.jsonl'; events.write_bytes(support.event(1))
            cursor = subscribers/'module-notifications.cursor'; cursor.write_text('0\n')
            (subscribers/'module-notifications.filter').write_text('*\n')
            # Redirect fixed fixture paths for an ordinary non-root host test.
            worker = source/'modules/notifications/scripts/worker.sh'
            worker.write_text(worker.read_text().replace('/opt/project-atlas', str(source))
                .replace(support.NOTIFY_ROOT, str(state)))
            processor = source/'modules/notifications/src/processor.py'
            processor.write_text(processor.read_text().replace(support.NOTIFY_ROOT, str(state)))
            env = {'PATH': os.environ['PATH'], 'PYTHONDONTWRITEBYTECODE': '1',
                'ATLAS_EVENT_DIR': str(runtime), 'ATLAS_NOTIFICATIONS_INTERVAL': '60'}
            for count in (1, 2):
                process = subprocess.Popen(['bash', str(worker)], env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    wait_for(lambda: cursor.read_text().strip() == str(count)
                        and (state/'worker-heartbeat').exists(), process)
                    process.send_signal(signal.SIGTERM)
                    self.assertEqual(process.wait(timeout=3), 0)
                    rows = [json.loads(line) for line in (state/'logs/notifications.log').read_text().splitlines()]
                    self.assertEqual([row['event_id'] for row in rows],
                        ['evt-four-service-'+str(n) for n in range(1, count+1)])
                    self.assertEqual(cursor.read_text().strip(), str(count))
                finally: cleanup(process)
                if count == 1:
                    with events.open('ab') as stream: stream.write(support.event(2))

    def test_notifications_stop_finishes_admitted_batch_without_consuming_later_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); support.stage(native, root)
            source = root/'source'; state = root/'notifications'; state.mkdir()
            runtime = root/'runtime'; subscribers = runtime/'subscribers'; subscribers.mkdir(parents=True)
            events = runtime/'events.jsonl'; events.write_bytes(support.event(1))
            cursor = subscribers/'module-notifications.cursor'; cursor.write_text('0\n')
            (subscribers/'module-notifications.filter').write_text('*\n')
            worker = source/'modules/notifications/scripts/worker.sh'
            worker.write_text(worker.read_text().replace('/opt/project-atlas', str(source))
                .replace(support.NOTIFY_ROOT, str(state)))
            processor = source/'modules/notifications/src/processor.py'
            original = processor.with_name('fixture_actual_processor.py')
            original.write_text(processor.read_text().replace(support.NOTIFY_ROOT, str(state)))
            processor.write_text("#!/usr/bin/env python3\nimport runpy,time\nfrom pathlib import Path\n"
                +"root=Path("+repr(str(root))+")\n(root/'batch-ready').touch()\n"
                +"while not (root/'release').exists():time.sleep(.01)\n"
                +"runpy.run_path("+repr(str(original))+",run_name='__main__')\n")
            env = {'PATH': os.environ['PATH'], 'PYTHONDONTWRITEBYTECODE': '1',
                'ATLAS_EVENT_DIR': str(runtime), 'ATLAS_NOTIFICATIONS_INTERVAL': '60'}
            process = subprocess.Popen(['bash', str(worker)], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                wait_for((root/'batch-ready').exists, process)
                process.send_signal(signal.SIGTERM)
                time.sleep(.05)
                (root/'release').touch()
                self.assertEqual(process.wait(timeout=3), 0)
                self.assertEqual(cursor.read_text().strip(), '1')
                rows = [json.loads(line) for line in (state/'logs/notifications.log').read_text().splitlines()]
                self.assertEqual([row['event_id'] for row in rows], ['evt-four-service-1'])
                # A new arrival after quiescence must remain pending.
                with events.open('ab') as stream: stream.write(support.event(2))
                self.assertEqual(cursor.read_text().strip(), '1')
            finally: cleanup(process)
