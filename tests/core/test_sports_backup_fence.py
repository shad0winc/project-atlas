"""Exercise actual shell writer ordering against an explicit stateful Docker stub."""
import fcntl
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('backup_fence_test', ROOT/'scripts/lib/sports-backup-fence.py')
support = importlib.util.module_from_spec(spec); spec.loader.exec_module(support)
spec = importlib.util.spec_from_file_location('backup_fence_component', ROOT/'scripts/diagnostics/sports-native-consumption-drill.py')
component = importlib.util.module_from_spec(spec); spec.loader.exec_module(component)


class BackupFenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atlas-backup-fence-test.', dir='/tmp')
        self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.ids = [str(index)*64 for index in range(1, 5)]
        self.state = self.root/'state.json'
        self.state.write_text(json.dumps({'running': {name: True for name in self.ids}, 'events': [], 'bad': ''}))
        self.executable = self.root/'docker'
        self.executable.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
p=Path('''+repr(str(self.state))+''');s=json.loads(p.read_text())
op=sys.argv[1];name=sys.argv[-1]
assert name in s['running']
s['events'].append([op,name]);result=''
if op=='stop':s['running'][name]=False
elif op=='start':s['running'][name]=True
elif op=='inspect':
 if '.State.ExitCode' in sys.argv[3]:
  result=('true|running|0|false' if s['running'][name] else 'false|exited|0|false')
  if s['bad']==name:result='false|exited|137|false'
 else:result='running' if s['running'][name] else 'stopped'
else:raise AssertionError('Unexpected stub Docker operation')
p.write_text(json.dumps(s))
if result:print(result)
''')
        self.executable.chmod(0o755)
        self.control = tempfile.TemporaryDirectory(prefix='atlas-backup-fence.', dir='/tmp')
        self.addCleanup(self.control.cleanup); self.control_path = Path(self.control.name)

    def read(self): return json.loads(self.state.read_text())

    def run_controller(self, capture=lambda: None, stopped=lambda: None, resumed=lambda: None):
        return support.controller(self.control_path, self.ids, capture, stopped, resumed,
                                  docker_executable=self.executable)

    def held(self):
        self.assertTrue((self.control_path/'maintenance').is_file())
        self.assertTrue((self.control_path/'owner').is_file())

    def test_four_stopped_during_capture_then_reverse_start_and_release(self):
        phases = []
        def stopped(): self.assertFalse(any(self.read()['running'].values()))
        def capture():
            stopped(); phases.append('capture')
            with (self.control_path/'deployment-scheduler.lock').open('rb') as stream:
                with self.assertRaises(BlockingIOError): fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def resumed():
            self.assertTrue(all(self.read()['running'].values())); phases.append('resumed')
            self.held()
        self.run_controller(capture, stopped, resumed)
        events = self.read()['events']
        self.assertEqual([row[1] for row in events if row[0]=='stop'], self.ids)
        self.assertEqual([row[1] for row in events if row[0]=='start'], list(reversed(self.ids)))
        self.assertEqual(phases, ['capture', 'resumed'])
        self.assertFalse((self.control_path/'maintenance').exists())

    def test_capture_failure_retains_controls_and_all_four_stopped(self):
        def broken(): raise ValueError('synthetic capture failure')
        with self.assertRaises(ValueError): self.run_controller(broken)
        self.held(); self.assertFalse(any(self.read()['running'].values()))
        self.assertFalse(any(row[0]=='start' for row in self.read()['events']))

    def test_restart_during_capture_is_refused_by_real_post_backup_recheck(self):
        def restart():
            state = self.read(); state['running'][self.ids[-1]] = True
            self.state.write_text(json.dumps(state))
        with self.assertRaises(ValueError): self.run_controller(restart)
        self.held()
        self.assertFalse(any(row[0]=='start' for row in self.read()['events']))

    def test_unclean_stop_blocks_capture_and_later_writer_stop(self):
        state = self.read(); state['bad'] = self.ids[1]; self.state.write_text(json.dumps(state))
        captured = []
        with self.assertRaises(ValueError): self.run_controller(lambda: captured.append(True))
        self.held(); self.assertFalse(captured)
        self.assertEqual([row[1] for row in self.read()['events'] if row[0]=='stop'], self.ids[:2])

    def test_post_restart_acceptance_failure_cannot_release_controls(self):
        def broken(): raise ValueError('synthetic readiness failure')
        with self.assertRaises(ValueError): self.run_controller(resumed=broken)
        self.held(); self.assertTrue(all(self.read()['running'].values()))

    def test_nonprivate_root_and_nonfull_identifiers_are_refused(self):
        self.control_path.chmod(0o755)
        with self.assertRaises(ValueError): self.run_controller()
        self.control_path.chmod(0o700)
        with self.assertRaises(ValueError):
            support.controller(self.control_path, ['atlas-api']*4, lambda: None, lambda: None, lambda: None)
        self.assertFalse(self.read()['events'])

    def test_capture_callback_requires_complete_orchestration_mode(self):
        with self.assertRaises(RuntimeError): component.run(capture_boundary=lambda *args: None)
        with self.assertRaises(RuntimeError): component.run(capture_boundary='bad', orchestrate_recovery=lambda *args: None)

    def test_cold_counter_requires_only_main_database_and_rejects_seed_files_or_sidecars(self):
        volume = self.root/'volume'; volume.mkdir(mode=0o700)
        database = volume/'state.db'; database.write_bytes(b'explicit-unit-counter')
        self.assertEqual(support.counter_file(volume), database)
        for extra in ('.gitkeep', 'image-seed', 'state.db-wal', 'state.db-shm', 'state.db-journal'):
            with self.subTest(extra=extra):
                entry = volume/extra; entry.write_bytes(b'explicit-unexpected-fixture')
                with self.assertRaises(ValueError): support.counter_file(volume)
                entry.unlink()
        database.unlink(); database.symlink_to(self.state)
        with self.assertRaises(ValueError): support.counter_file(volume)


if __name__ == '__main__': unittest.main()
