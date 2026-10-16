"""Strict native restore subprocess behavior without requiring PostgreSQL in CI."""
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('postgres_drill', ROOT / 'scripts/lib/sports-postgres-recovery-drill.py')
drill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drill)


class PostgresRecoveryDrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.dump'
        self.path.write_bytes(b'PGDMP' + b'fixture')

    def test_any_nonzero_exit_is_fatal_even_for_warning_text(self):
        result = subprocess.CompletedProcess([], 1, b'partial success', b'warning only')
        with patch.object(drill.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(drill.DrillFailure, '^command-failed$'):
                drill.command(['/fixed/pg_restore'], env={})

    def test_timeout_is_sanitized(self):
        failure = subprocess.TimeoutExpired('private connection', 1, output=b'private', stderr=b'private')
        with patch.object(drill.subprocess, 'run', side_effect=failure):
            with self.assertRaisesRegex(drill.DrillFailure, '^command-timeout$'):
                drill.command(['/fixed/pg_restore'], env={})

    def test_missing_binary_is_sanitized(self):
        with patch.object(drill.subprocess, 'run', side_effect=OSError('private value')):
            with self.assertRaisesRegex(drill.DrillFailure, '^command-unavailable$'):
                drill.command(['/fixed/pg_restore'], env={})

    def test_restore_preflights_archive_then_requires_atomic_strict_exit(self):
        with patch.object(drill, 'command', return_value=b'') as call:
            drill.strict_restore(Path('/fixed/pg_restore'), self.path, 'atlas_drill_target', env={'PGHOST': '/private/socket'})
        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args_list[0].args[0], ['/fixed/pg_restore', '--list', str(self.path)])
        restore = call.call_args_list[1].args[0]
        self.assertIn('--single-transaction', restore)
        self.assertIn('--exit-on-error', restore)
        self.assertIn('--no-owner', restore)
        self.assertIn('--no-privileges', restore)
        self.assertNotIn('--clean', restore)

    def test_invalid_archive_never_reaches_restore(self):
        with patch.object(drill, 'command', side_effect=drill.DrillFailure('command-failed')) as call:
            with self.assertRaises(drill.DrillFailure):
                drill.strict_restore(Path('/fixed/pg_restore'), self.path, 'atlas_drill_target', env={})
        self.assertEqual(call.call_count, 1)
        self.assertIn('--list', call.call_args.args[0])

    def test_arbitrary_database_names_are_rejected_without_commands(self):
        for database in ('dispatcharr', 'postgres', 'atlas_drill_target; DROP DATABASE x', '--host=external'):
            with self.subTest(database=database), patch.object(drill, 'command') as call:
                with self.assertRaises(drill.DrillFailure):
                    drill.strict_restore(Path('/fixed/pg_restore'), self.path, database, env={})
                call.assert_not_called()

    def test_links_bad_header_and_oversize_are_rejected(self):
        for kind in ('link', 'header', 'size', 'hardlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as name:
                root = Path(name); path = root / 'dump'
                if kind == 'link':
                    path.symlink_to(self.path)
                else:
                    path.write_bytes(b'bad' if kind == 'header' else b'PGDMPfixture')
                    if kind == 'size':
                        with path.open('ab') as handle: handle.truncate(drill.MAX_DUMP_BYTES + 1)
                    if kind == 'hardlink': os.link(path, root / 'linked')
                with patch.object(drill, 'command') as call:
                    with self.assertRaises(drill.DrillFailure):
                        drill.strict_restore(Path('/fixed/pg_restore'), path, 'atlas_drill_target', env={})
                    call.assert_not_called()

    def test_drill_refuses_root_or_absent_optin_before_cluster_creation(self):
        for uid, enabled in ((0, '1'), (65534, '')):
            with self.subTest(uid=uid), patch.object(drill.os, 'geteuid', return_value=uid), \
                 patch.dict(os.environ, {'ATLAS_SYNTHETIC_RECOVERY_DRILL': enabled}), \
                 patch.object(drill, 'binaries') as binaries:
                with self.assertRaises(drill.DrillFailure): drill.drill()
                binaries.assert_not_called()

    def test_main_does_not_print_raw_errors(self):
        output = io.StringIO()
        with patch.object(drill, 'drill', side_effect=RuntimeError('private-connection-data')), \
             patch.object(drill.sys, 'stderr', output):
            self.assertEqual(drill.main(), 1)
        self.assertEqual(output.getvalue(), 'SYNTHETIC_POSTGRES_RECOVERY_DRILL=FAIL category=RuntimeError\n')


class HostDrillBoundaryTests(unittest.TestCase):
    def test_host_runner_uses_only_isolated_synthetic_container(self):
        spec = importlib.util.spec_from_file_location('host_drill', ROOT / 'scripts/diagnostics/sports-native-recovery-drill.py')
        host = importlib.util.module_from_spec(spec); spec.loader.exec_module(host)
        receipt = {'version': 1, 'scope': 'synthetic-isolated-postgres-only',
            'restore_data': 'pass', 'nonzero_exit_rejected': 'pass',
            'single_transaction_rollback': 'pass', 'corrupt_archive_rejected': 'pass',
            'postgres_stopped': 'pass', 'production_state_access': False}
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts/lib').mkdir(parents=True)
            (root / 'scripts/lib/sports-postgres-recovery-drill.py').write_bytes(
                (ROOT / 'scripts/lib/sports-postgres-recovery-drill.py').read_bytes())
            pointer = root / 'current'; pointer.write_text(host.DEPLOYMENT + '\n')
            def path(value):
                if value == '/mnt/storage/configs/atlas/deployments/current': return pointer
                return Path(value)
            responses = [subprocess.CompletedProcess([], 0, json.dumps(receipt).encode(), b''),
                         subprocess.CompletedProcess([], 1, b'', b'not found')]
            with patch.object(host, '__file__', str(root / 'scripts/diagnostics/drill.py')), \
                 patch.object(host, 'Path', side_effect=path), \
                 patch.object(host.subprocess, 'check_output', return_value=b'8795962651877c25b70460d3863187efa0cafed3') as git, \
                 patch.object(host, 'production_observation', return_value=host.IMAGE + '|true|unchanged') as observation, \
                 patch.object(host, 'docker', side_effect=[host.IMAGE, '1.0']) as docker, \
                 patch.object(host.subprocess, 'run', side_effect=responses) as run, \
                 patch('builtins.print'):
                # check_output was requested with text=True.
                git.return_value = '8795962651877c25b70460d3863187efa0cafed3'
                host.run()
            arguments = run.call_args_list[0].args[0]
            for flag in ('--network=none', '--read-only', '--user=65534:65534', '--cap-drop=ALL',
                         '--security-opt=no-new-privileges', '--pull=never', '--no-healthcheck'):
                self.assertIn(flag, arguments)
            for forbidden in ('--mount', '--volume', '-v', '--volumes-from', '--env-file', '--privileged'):
                self.assertNotIn(forbidden, arguments)
            self.assertEqual(arguments[-4:], [host.IMAGE, '-I', '-B', '-'])
            self.assertEqual(observation.call_count, 2)
            self.assertEqual(pointer.read_text(), host.DEPLOYMENT + '\n')
            self.assertEqual(docker.call_count, 2)


if __name__ == '__main__': unittest.main()
