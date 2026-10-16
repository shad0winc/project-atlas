"""Native adapter contracts without PostgreSQL or Docker dependencies in Core CI."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pg_prepare', ROOT / 'scripts/lib/sports-postgres-prepare.py')
adapter = importlib.util.module_from_spec(spec); spec.loader.exec_module(adapter)
TOC = b'''5; 2615 2200 SCHEMA - public pg_database_owner
20; 1259 1234 TABLE public aa_first app
21; 1259 1235 TABLE public zz_tail app
30; 0 1234 TABLE DATA public aa_first app
31; 0 1235 TABLE DATA public zz_tail app
'''


class NativePrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_archive_table_plan_distinguishes_definitions_from_data(self):
        self.assertEqual(adapter.archive_plan(TOC), (True, ['aa_first', 'zz_tail']))
        self.assertEqual(adapter.archive_plan(b'\n'.join(TOC.splitlines()[1:]) + b'\n'),
                         (False, ['aa_first', 'zz_tail']))

    def test_nonpublic_and_nonstandard_or_duplicate_table_plans_are_rejected(self):
        for raw in (TOC.replace(b'SCHEMA - public', b'SCHEMA - other'),
                    TOC.replace(b'TABLE public aa_first', b'TABLE other aa_first'),
                    TOC.replace(b'TABLE public aa_first', b'TABLE public "space-name"'),
                    TOC + b'40; 1259 1236 TABLE public aa_first app\n', b'; empty archive\n'):
            with self.subTest(raw=raw[:50]), self.assertRaises(adapter.PrepareError):
                adapter.archive_plan(raw)

    def test_identifiers_reject_sql_and_shell_metacharacters(self):
        for name in ('a;DROP DATABASE b', 'a\ncommand', '../db', 'a b', '$(id)', '', 'x' * 64):
            with self.subTest(name=name), self.assertRaises(adapter.PrepareError): adapter.identifier(name)
        self.assertEqual(adapter.identifier('atlas_app_1'), 'atlas_app_1')

    def test_cluster_copy_preserves_source_and_produces_private_independent_files(self):
        source = self.root / 'source'; source.mkdir(mode=0o700)
        (source / 'global').mkdir(mode=0o700)
        (source / 'PG_VERSION').write_bytes(b'17\n')
        (source / 'global/pg_control').write_bytes(b'fixture-control')
        before = adapter.cluster_digest(source)
        destination = self.root / 'target'
        adapter.copy_cluster(source, destination)
        self.assertEqual(adapter.cluster_digest(source), before)
        self.assertEqual(adapter.cluster_digest(destination), before)
        (destination / 'global/pg_control').write_bytes(b'changed-clone')
        self.assertEqual(adapter.cluster_digest(source), before)
        self.assertEqual((destination / 'global/pg_control').stat().st_mode & 0o777, 0o600)

    def test_cluster_links_and_entry_budgets_fail_before_copy(self):
        source = self.root / 'source'; source.mkdir(mode=0o700)
        payload = source / 'payload'; payload.write_bytes(b'fixture')
        for kind in ('link', 'hardlink', 'size'):
            link = source / 'linked'
            with self.subTest(kind=kind):
                if kind == 'link': link.symlink_to(payload)
                if kind == 'hardlink': os.link(payload, link)
                budget = 1 if kind == 'size' else adapter.MAX_CLUSTER_BYTES
                with patch.object(adapter, 'MAX_CLUSTER_BYTES', budget):
                    with self.assertRaises(adapter.PrepareError): adapter.copy_cluster(source, self.root / ('target-' + kind))
                if link.exists() or link.is_symlink(): link.unlink()

    def test_dirty_or_running_cluster_is_not_a_cold_input(self):
        cluster = self.root / 'cluster'; cluster.mkdir(mode=0o700)
        for state in ('in production', 'shut down in recovery', 'starting up'):
            output = ('Database cluster state:               ' + state + '\n').encode()
            with self.subTest(state=state), patch.object(adapter, 'command', return_value=output):
                with self.assertRaises(adapter.PrepareError): adapter.cold_state(cluster, {'pg_controldata': Path('/fixed/tool')}, {})
        (cluster / 'postmaster.pid').write_text('fixture')
        with patch.object(adapter, 'command') as command:
            with self.assertRaises(adapter.PrepareError): adapter.cold_state(cluster, {}, {})
            command.assert_not_called()

    def test_clean_stopped_cluster_is_accepted(self):
        cluster = self.root / 'cluster'; cluster.mkdir(mode=0o700)
        with patch.object(adapter, 'command', return_value=b'Database cluster state:               shut down\n'):
            adapter.cold_state(cluster, {'pg_controldata': Path('/fixed/tool')}, {})

    def test_any_nonzero_native_exit_is_fatal(self):
        with patch.object(adapter.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaisesRegex(adapter.PrepareError, '^native-command-failed$'):
                adapter.command(['/fixed/pg_restore'], env={'TMPDIR': str(self.root)})

    def test_native_timeout_and_unavailable_errors_are_sanitized(self):
        for error, category in ((subprocess.TimeoutExpired('private', 1), 'native-deadline'),
                                (OSError('private'), 'native-unavailable')):
            with self.subTest(category=category), patch.object(adapter.subprocess, 'run', side_effect=error):
                with self.assertRaisesRegex(adapter.PrepareError, '^' + category + '$'):
                    adapter.command(['/fixed/tool'], env={'TMPDIR': str(self.root)})

    def test_native_output_is_bounded(self):
        def run(*args, **kwargs):
            kwargs['stdout'].write(b'x' * 20)
            return subprocess.CompletedProcess([], 0)
        with patch.object(adapter, 'MAX_OUTPUT_BYTES', 10), patch.object(adapter.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(adapter.PrepareError, '^native-output-budget$'):
                adapter.command(['/fixed/tool'], env={'TMPDIR': str(self.root)})

    def test_root_cannot_run_native_preparation(self):
        with patch.object(adapter.os, 'geteuid', return_value=0), patch.object(adapter, 'command') as command:
            with self.assertRaisesRegex(adapter.PrepareError, '^nonroot-required$'):
                adapter.prepare(self.root, database='app', admin_role='app', dump_sha256='a' * 64)
            command.assert_not_called()

    def test_pg_version_symlink_is_not_followed(self):
        cluster = self.root / 'cluster'; cluster.mkdir(mode=0o700)
        (cluster / 'PG_VERSION').symlink_to(self.root / 'outside')
        with self.assertRaises(OSError): adapter.tools_for(cluster)

class NativePreparationPipelineTests(unittest.TestCase):
    def test_success_and_restore_role_or_stop_failure_receipts(self):
        import itertools
        for failure in ('none', 'restore', 'roles', 'stop'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(prefix='project-atlas-pg-prepare.', dir='/tmp') as directory:
                root = Path(directory); cold = root / 'cold-cluster'; cold.mkdir(mode=0o700)
                (cold / 'PG_VERSION').write_bytes(b'17\n')
                (cold / 'postgresql.conf').write_text('original-config')
                dump = root / 'database.dump'; dump.write_bytes(b'PGDMP-synthetic'); dump.chmod(0o600)
                before = adapter.cluster_digest(cold)
                tools = {name: Path('/fixed') / name for name in ('pg_ctl', 'pg_controldata', 'psql', 'pg_restore')}
                roles = 0
                stopped = []
                def command(args, **kwargs):
                    nonlocal roles
                    if args[0].endswith('pg_restore'):
                        if '--list' in args: return TOC
                        if '--schema-only' in args: return b'CREATE SCHEMA public;\n'
                        if failure == 'restore': raise adapter.PrepareError('native-command-failed')
                        self.assertIn('--exit-on-error', args); self.assertIn('--single-transaction', args)
                        return b''
                    if args[0].endswith('pg_ctl'):
                        if args[-1] == 'stop':
                            stopped.append(True)
                            if failure == 'stop': raise adapter.PrepareError('native-command-failed')
                        return b''
                    query = args[-1]
                    if 'rolsuper' in query: return b't\n'
                    if 'SELECT count(*) FROM pg_namespace' in query: return b'0\n'
                    if "json_build_object('roles'" in query:
                        roles += 1
                        return b'changed' if failure == 'roles' and roles == 2 else b'same-roles'
                    if 'row_to_json(t)' in query: return b'same-properties'
                    if 'json_agg(c.relname' in query: return b'["aa_first","zz_tail"]'
                    return b''
                uid = os.geteuid()
                with patch.object(adapter.os, 'geteuid', side_effect=itertools.chain([65534], itertools.repeat(uid))), \
                     patch.object(adapter, 'tools_for', return_value=('17', tools)), \
                     patch.object(adapter, 'cold_state'), patch.object(adapter, 'command', side_effect=command):
                    if failure == 'none':
                        receipt = adapter.prepare(root, database='app', admin_role='app', dump_sha256=hashlib.sha256(dump.read_bytes()).hexdigest())
                        self.assertFalse(receipt['ready_for_live_apply'])
                        self.assertTrue((root / 'PREPARED.json').exists())
                        self.assertTrue(receipt['global_roles_preserved'])
                        self.assertEqual(adapter.validate_prepared(root), receipt)
                        (root / 'restored-cluster/postgresql.conf').write_text('tampered')
                        with self.assertRaises(adapter.PrepareError): adapter.validate_prepared(root)
                    else:
                        with self.assertRaises(adapter.PrepareError):
                            adapter.prepare(root, database='app', admin_role='app', dump_sha256=hashlib.sha256(dump.read_bytes()).hexdigest())
                        self.assertFalse((root / 'PREPARED.json').exists())
                self.assertEqual(adapter.cluster_digest(cold), before)
                self.assertTrue(stopped)


class NativePrepareHostBoundaryTests(unittest.TestCase):
    def test_host_runs_only_owned_isolated_container_with_pinned_sources(self):
        import json
        spec = importlib.util.spec_from_file_location('native_prepare_host', ROOT / 'scripts/diagnostics/sports-native-restore-prepare-drill.py')
        host = importlib.util.module_from_spec(spec); spec.loader.exec_module(host)
        receipt = {'version': 1, 'scope': 'synthetic-native-restore-preparation',
            'restore_data': 'pass', 'stale_objects_removed': 'pass', 'grants_restored': 'pass',
            'global_roles_preserved': 'pass', 'cold_source_unchanged': 'pass',
            'startup_hooks_isolated': 'pass', 'startup_config_preserved': 'pass',
            'corrupt_archive_rejected': 'pass', 'clusters_stopped': 'pass',
            'production_state_access': False, 'live_restore_enabled': False}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'scripts/lib').mkdir(parents=True)
            for name in ('sports-postgres-prepare.py', 'sports-postgres-prepare-drill.py'):
                (root / 'scripts/lib' / name).write_bytes((ROOT / 'scripts/lib' / name).read_bytes())
            pointer = root / 'current'; pointer.write_text(host.DEPLOYMENT + '\n')
            def path(value):
                return pointer if value == '/mnt/storage/configs/atlas/deployments/current' else Path(value)
            responses = [subprocess.CompletedProcess([], 0, json.dumps(receipt).encode(), b''),
                         subprocess.CompletedProcess([], 1, b'', b'not found')]
            with patch.object(host, '__file__', str(root / 'scripts/diagnostics/drill.py')), \
                 patch.object(host, 'Path', side_effect=path), \
                 patch.object(host.subprocess, 'check_output', return_value='be41d82819441c8be7457ebcd351d40221120208'), \
                 patch.object(host, 'production_observation', return_value=host.IMAGE + '|true|unchanged') as observe, \
                 patch.object(host, 'docker', side_effect=[host.IMAGE, '1.0']), \
                 patch.object(host.subprocess, 'run', side_effect=responses) as run, patch('builtins.print'):
                host.run()
            arguments = run.call_args_list[0].args[0]
            for flag in ('--network=none', '--read-only', '--user=65534:65534', '--cap-drop=ALL',
                         '--security-opt=no-new-privileges', '--pull=never', '--no-healthcheck'):
                self.assertIn(flag, arguments)
            for flag in ('--mount', '--volume', '-v', '--volumes-from', '--env-file', '--privileged'):
                self.assertNotIn(flag, arguments)
            self.assertEqual(arguments[-5:-1], [host.IMAGE, '-I', '-B', '-c'])
            sources = json.loads(run.call_args_list[0].kwargs['input'])
            self.assertEqual(set(sources), {'adapter', 'drill'})
            for source in sources.values():
                self.assertIn(hashlib.sha256(source.encode()).hexdigest(), arguments[-1])
            self.assertEqual(observe.call_count, 2)
            self.assertEqual(pointer.read_text(), host.DEPLOYMENT + '\n')


if __name__ == '__main__': unittest.main()
