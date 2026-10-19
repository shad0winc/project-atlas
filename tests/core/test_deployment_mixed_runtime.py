"""Behavioral coverage for the bounded mixed Sports deployment contract."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('deployment_mixed', ROOT / 'scripts/lib/deployment-mixed-runtime.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class MixedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.records = self.root / 'records'
        self.record = self.records / 'baseline-test'
        self.record.mkdir(parents=True)
        self.generation = self.root / 'source'
        self.generation.mkdir()
        self.old, self.new, self.historical = 'a' * 40, 'b' * 40, 'c' * 40
        self.files = {
            'modules/sports/Dockerfile.private-api': (
                b'COPY modules/sports/src/private_api.py /srv/sports/private_api.py\n'
                b'COPY modules/sports/src/providers /srv/sports/providers\n'),
            'modules/sports/src/private_api.py': b'pass\n',
            'modules/sports/src/providers/thesportsdb.py': b'provider=True\n',
            'config/atlas.conf': b'CONFIG=value\n',
            'config/modules/modules.conf': b'ENABLED=true\n',
        }
        for name, raw in self.files.items():
            p = self.generation / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        (self.generation / '.env').write_bytes(b'PRIVATE=fixture\n')
        for name in ('modules/sports/.env', 'modules/notifications/.env'):
            p = self.generation / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'PRIVATE=fixture\n')
        for component, commit in (('core', self.old), ('ingress', self.old), ('sports', self.new)):
            self.archive(self.record / (component + '-source.tar.gz'), commit)
        shutil.copyfile(self.record / 'sports-source.tar.gz', self.record / 'sports-writer-source.tar.gz')
        metadata = {'type': 'baseline', 'baseline_kind': 'linked-repair-mixed-runtime-reconciliation',
                    'failed_deployment': 'original-failed', 'previous_baseline': 'original-baseline',
                    'core_commit': self.old, 'ingress_commit': self.old, 'sports_commit': self.new,
                    'source_commit': self.old, 'scheduler_commit': self.old,
                    'notifications_commit': self.historical, 'source_claim': M.SOURCE_CLAIM, **M.MARKERS}
        self.write_metadata(self.record, metadata)
        (self.record / 'status').write_text('verified\n')
        (self.record / 'images.tsv').write_text(
            'ingress|stack/ingress.yml|atlas-ingress|sports-writer|/atlas-sports-writer|tag|sha256:writer\n'
            'sports|modules/sports/docker-compose.yml|sports|atlas-sports-controller|/atlas-sports-controller|tag|sha256:controller\n')
        copies = M.expected_copies(M.archive_files(self.record / 'sports-source.tar.gz'))
        ledger = {'schema_version': 1, 'component_commits_describe_base_recipes': True,
            'core': {'recipe_commit': self.old},
            'ingress': {'recipe_commit': self.old, 'default_application_source_commit': self.old,
                'overrides': {'sports-writer': {'code_commit': self.new, 'image': 'sha256:writer',
                    'source_archive': 'sports-writer-source.tar.gz', 'copied_file_sha256': copies}}},
            'sports': {'recipe_commit': self.new, 'controller_source_commit': self.new,
                'controller_image': 'sha256:controller', 'active_controller_source': str(self.generation)},
            'notifications': {'source_commit': self.historical, 'source_mode': 'historical',
                              'source_checkout': '/opt/project-atlas'},
            'scheduler': {'source_commit': self.old, 'publication_archive': 'core-source.tar.gz'}}
        self.json('service-sources.json', ledger)
        self.json('repair-tracked-source.json', {'commit': self.new, 'files': [
            {'path': name, 'mode': '100644', 'oid': hashlib.sha1(
                b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
            for name, raw in self.files.items()]})
        overlay = {}
        for name in sorted(M.CONFIGURATION):
            p = self.generation / name
            st = p.stat()
            overlay[name] = {'sha256': M.digest(p), 'uid': st.st_uid, 'gid': st.st_gid,
                             'mode': oct(st.st_mode & 0o777)}
        self.json('repair-activation.json', {'source_commit': self.new,
            'source_generation': str(self.generation), 'configuration_overlay': overlay,
            'target_source_archive_sha256': M.digest(self.record / 'sports-source.tar.gz')})
        (self.record / 'original-lock-owner').write_text('deployment_id=original-failed\n')
        self.json('recovery-chain.json', {'schema_version': 1,
            'original_failed_transaction': 'original-failed', 'previous_verified_baseline': 'original-baseline',
            'original_lock_owner_sha256': M.digest(self.record / 'original-lock-owner')})
        self.json('accepted-private-sustained.json', {'accepted': True, 'source_commit': self.new})
        (self.record / 'backup_file').write_text('/private/retained-backup.tar.gz\n')
        M.seal(self.record)

    def archive(self, path, commit):
        with tarfile.open(path, 'w:gz', format=tarfile.PAX_FORMAT, pax_headers={'comment': commit}) as archive:
            for name, raw in self.files.items():
                member = tarfile.TarInfo(name)
                member.mode = 0o644
                member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))

    def json(self, name, value):
        (self.record / name).write_text(json.dumps(value))

    def update_json(self, name, change):
        value = json.loads((self.record / name).read_text())
        change(value)
        self.json(name, value)
        M.seal(self.record)

    @staticmethod
    def write_metadata(path, values):
        (path / 'metadata').write_text(''.join(k + '=' + v + '\n' for k, v in values.items()))

    def inspect(self, name):
        return {'Image': 'sha256:writer' if name.endswith('writer') else 'sha256:controller',
                'State': {'Running': True}, 'Mounts': [{'Destination': '/opt/project-atlas',
                 'Source': str(self.generation), 'Type': 'bind', 'RW': False}]}

    def live(self, excluded=''):
        with patch.object(M, 'inspect', side_effect=self.inspect), patch.object(M.subprocess, 'run') as run:
            run.return_value.returncode = 0
            M.check_live(self.record, excluded)

    def test_valid_record_and_live_sources(self):
        M.check_record(self.record)
        self.live()

    def test_archive_tampering_rejected(self):
        with (self.record / 'core-source.tar.gz').open('ab') as stream:
            stream.write(b'tampered')
        with self.assertRaises(ValueError):
            M.check_record(self.record)

    def test_archive_commit_marker_checked_even_after_reseal(self):
        self.archive(self.record / 'core-source.tar.gz', self.new)
        M.seal(self.record)
        with self.assertRaises(ValueError):
            M.check_record(self.record)

    def test_missing_ledger_cannot_be_resealed_as_valid(self):
        (self.record / 'service-sources.json').unlink()
        M.seal(self.record)
        with self.assertRaises(ValueError):
            M.check_record(self.record)

    def test_writer_copy_map_bound_to_archive(self):
        self.update_json('service-sources.json', lambda x: x['ingress']['overrides']['sports-writer'][
            'copied_file_sha256'].update({'/srv/sports/providers/thesportsdb.py': '0' * 64}))
        with self.assertRaises(ValueError):
            M.check_record(self.record)

    def test_tracked_blob_manifest_bound_to_archive(self):
        self.update_json('repair-tracked-source.json', lambda x: x['files'][0].update({'oid': '0' * 40}))
        with self.assertRaises(ValueError):
            M.check_record(self.record)

    def test_unknown_source_override_refused(self):
        self.update_json('service-sources.json', lambda x: x['ingress']['overrides'].update({'api': {}}))
        with self.assertRaises(ValueError):
            M.check_record(self.record)

    def test_scheduler_source_cannot_be_relabelled(self):
        values = M.metadata(self.record)
        values['scheduler_commit'] = self.new
        self.write_metadata(self.record, values)
        M.seal(self.record)
        with self.assertRaises(ValueError):
            M.check_record(self.record)

    def test_native_recovery_subdirectories_are_retained(self):
        (self.record / 'recovery-sports.abc123').mkdir()
        M.seal(self.record)
        M.check_record(self.record)

    def test_unexpected_subdirectory_refused(self):
        (self.record / 'unexpected').mkdir()
        with self.assertRaises(ValueError):
            M.seal(self.record)

    def test_evidence_symlink_refused(self):
        p = self.record / 'accepted-private-sustained.json'
        p.unlink()
        p.symlink_to(self.generation / '.env')
        with self.assertRaises(OSError):
            M.check_record(self.record)

    def test_inheritance_preserves_repair_and_reconciliation_transaction(self):
        dest = self.records / 'new-reconciliation'
        dest.mkdir()
        for p in self.record.iterdir():
            if p.name not in M.SUPPLEMENTS and p.name != 'MANIFEST.sha256':
                shutil.copyfile(p, dest / p.name)
        (dest / 'backup_file').unlink()
        values = M.metadata(dest)
        values['failed_deployment'] = 'recent-failed'
        values['baseline_kind'] = 'rollback-reconciliation'
        values['previous_baseline'] = 'baseline-test'
        self.write_metadata(dest, values)
        M.inherit(self.record, dest)
        M.check_record(dest)
        self.assertEqual(M.metadata(dest)['failed_deployment'], 'original-failed')
        self.assertEqual(M.metadata(dest)['reconciliation_transaction'], 'recent-failed')
        self.assertEqual((dest / 'backup_file').read_bytes(), (self.record / 'backup_file').read_bytes())
        self.assertEqual((dest / 'service-sources.json').read_bytes(), (self.record / 'service-sources.json').read_bytes())

    def test_restore_materializes_exact_private_overlay(self):
        dest = self.records / 'update-test' / 'recovery-sports.fixture'
        dest.mkdir(parents=True)
        M.prepare_restore(self.record, dest)
        self.assertEqual((dest / '.env').read_bytes(), (self.generation / '.env').read_bytes())
        self.assertEqual((dest / 'config/atlas.conf').stat().st_mode & 0o777,
                         (self.generation / 'config/atlas.conf').stat().st_mode & 0o777)

    def test_reconciliation_uses_immediate_transaction_rollback_references(self):
        dest = self.records / 'new-reconciliation'
        dest.mkdir()
        for p in self.record.iterdir():
            if p.name not in M.SUPPLEMENTS and p.name != 'MANIFEST.sha256':
                shutil.copyfile(p, dest / p.name)
        transaction = self.records / 'update-test'
        transaction.mkdir()
        for name in ('backup_file', 'pre-images.tsv', 'rollback-images.tsv'):
            (transaction / name).write_text('immediate-' + name + '\n')
        M.inherit(self.record, dest, transaction)
        M.check_record(dest)
        for name in ('backup_file', 'pre-images.tsv', 'rollback-images.tsv'):
            self.assertEqual((dest / name).read_bytes(), (transaction / name).read_bytes())

    def test_restore_rejects_destination_outside_native_namespace(self):
        dest = self.root / 'outside'
        dest.mkdir()
        with self.assertRaises(ValueError):
            M.prepare_restore(self.record, dest)
        self.assertEqual(list(dest.iterdir()), [])

    def test_restore_refuses_modified_preserved_configuration(self):
        (self.generation / '.env').write_bytes(b'changed')
        dest = self.records / 'update-test' / 'recovery-sports.fixture'
        dest.mkdir(parents=True)
        with self.assertRaises(ValueError):
            M.prepare_restore(self.record, dest)
        self.assertEqual(list(dest.iterdir()), [])

    def test_changed_controller_source_is_refused(self):
        (self.generation / 'modules/sports/src/private_api.py').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.live()

    def test_writer_content_failure_is_refused(self):
        with patch.object(M, 'inspect', side_effect=self.inspect), patch.object(M.subprocess, 'run') as run:
            run.return_value.returncode = 1
            with self.assertRaises(ValueError):
                M.check_live(self.record)

    def test_writable_controller_mount_refused(self):
        def bad(name):
            row = self.inspect(name)
            row['Mounts'][0]['RW'] = True
            return row
        with patch.object(M, 'inspect', side_effect=bad), patch.object(M.subprocess, 'run') as run:
            run.return_value.returncode = 0
            with self.assertRaises(ValueError):
                M.check_live(self.record)

    def test_sports_exclusion_keeps_writer_check_and_skips_controller(self):
        with patch.object(M, 'inspect', side_effect=self.inspect) as inspect, patch.object(M.subprocess, 'run') as run:
            run.return_value.returncode = 0
            M.check_live(self.record, 'sports')
            self.assertEqual(inspect.call_args_list, [(('atlas-sports-writer',),)])
            self.assertEqual(run.call_count, 1)

    def shell(self, body):
        env = os.environ.copy()
        env.update({'ATLAS_PROJECT_DIR': str(ROOT), 'RECORD': str(self.record),
                    'DEPLOYMENT_FILE': str(ROOT / 'scripts/commands/deployment.sh'),
                    'UPDATE_FILE': str(ROOT / 'scripts/commands/update.sh')})
        return subprocess.run(['bash', '-c', 'set -euo pipefail\nsource "$DEPLOYMENT_FILE"\n' + body],
                              env=env, capture_output=True, text=True)

    def test_partial_update_guard_refuses_both_partial_scopes(self):
        for scope in ('core', 'ingress'):
            with self.subTest(scope=scope):
                result = self.shell('atlas_deployment_validate_update_inheritance "$RECORD" ' + scope)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('partial updates', result.stderr)

    def test_all_update_inheritance_allowed(self):
        self.assertEqual(self.shell('atlas_deployment_validate_update_inheritance "$RECORD" all').returncode, 0)

    def test_baseline_creation_refuses_held_recovery_before_health_checks(self):
        result = self.shell(r'''
atlas_deployment_validate_source() { :; }
atlas_deployment_lock_dir() { printf '%s\n' "$RECORD"; }
atlas_command_doctor() { echo UNEXPECTED_DOCTOR; }
atlas_deployment_baseline
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNEXPECTED', result.stdout)

    def test_baseline_creation_cannot_erase_mixed_provenance(self):
        result = self.shell(r'''
atlas_deployment_validate_source() { :; }
atlas_deployment_lock_dir() { printf '%s\n' "$RECORD/no-lock"; }
atlas_deployment_current_id() { echo baseline-test; }
atlas_deployment_record_dir() { printf '%s\n' "$RECORD"; }
atlas_command_doctor() { echo UNEXPECTED_DOCTOR; }
atlas_deployment_baseline
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNEXPECTED', result.stdout)

    def test_manifest_detects_lost_marker_and_missing_ledger(self):
        for p in list(self.record.iterdir()):
            if p.name in M.SUPPLEMENTS:
                p.unlink()
        values = M.metadata(self.record)
        for key in M.MARKERS:
            values.pop(key)
        self.write_metadata(self.record, values)
        self.assertEqual(self.shell('atlas_deployment_is_mixed "$RECORD"').returncode, 0)

    def test_update_refuses_before_runtime_verification_and_durable_lock(self):
        result = self.shell(r'''
source "$UPDATE_FILE"
atlas_print_header() { :; }
atlas_update_validate_arguments() { :; }
atlas_deployment_validate_source() { :; }
atlas_deployment_require_current_record() { printf '%s\n' "$RECORD"; }
atlas_deployment_verify_runtime() { echo UNEXPECTED_RUNTIME_VERIFY; }
atlas_deployment_new_id() { echo UNEXPECTED_NEW_ID; }
atlas_deployment_acquire_lock() { echo UNEXPECTED_LOCK; }
atlas_update_execute_locked core --migration none
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNEXPECTED', result.stdout)

    def test_native_shell_syntax(self):
        for name in ('deployment.sh', 'update.sh'):
            result = subprocess.run(['bash', '-n', str(ROOT / 'scripts/commands' / name)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_git_archive_has_the_required_commit_marker(self):
        repo = self.root / 'git-fixture'
        repo.mkdir()
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, env=env)
        (repo / 'file').write_text('fixture\n')
        subprocess.run(['git', '-C', str(repo), 'add', 'file'], check=True, env=env)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Atlas Tests',
                        '-c', 'user.email=atlas-tests@example.invalid',
                        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture'], check=True, env=env)
        commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], env=env).decode().strip()
        archive = self.root / 'native-archive.tar.gz'
        subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar.gz',
                        '--output=' + str(archive), commit], check=True, env=env)
        self.assertEqual(set(M.archive_files(archive, commit)), {'file'})

    def test_untracked_controller_python_source_refused(self):
        (self.generation / 'sitecustomize.py').write_text('pass\n')
        with self.assertRaises(ValueError):
            self.live()


if __name__ == '__main__':
    unittest.main()
