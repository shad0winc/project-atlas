"""Schema-2 evidence refuses corruption, downgrade, and premature live use."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import unittest
from unittest.mock import patch

from tests.core import test_deployment_mixed_runtime as legacy

M = legacy.M
E = M.extension_module()
ROOT = Path(__file__).resolve().parents[2]


class IngressExtensionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy.MixedRuntimeTests('test_valid_record_and_live_sources')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.record = self.fixture.record
        self.source_commit, self.release_commit = 'd' * 40, 'e' * 40
        self.files = {
            'apps/api/Dockerfile': b'FROM python:3.12-slim\nCOPY apps/api /srv\n',
            'apps/portal/Dockerfile': b'FROM node:22-alpine AS base\nFROM node:22-alpine AS runner\nCOPY apps/portal /app\n',
            'atlas/maintenance_control_server.py': b'fixture=True\n',
            'infra/caddy/Caddyfile': b'import sites/*\n',
            'infra/caddy/site/admin.js': b'// fixture\n',
            'systemd/atlas-maintenance-control.service': (
                b'WorkingDirectory=/opt/project-atlas-v1-main\n'
                b'Environment=PYTHONPATH=/opt/project-atlas-v1-main\n'
                b'ExecStart=/usr/bin/python3 -B -m atlas.maintenance_control_server\n'),
        }
        self.archive()
        self.tree = E.tree_oid(M.archive_files(self.record / 'ingress-application-source.tar.gz'))
        tracked = {'commit': self.source_commit, 'tree': self.tree, 'files': [
            {'path': name, 'mode': '100644', 'oid': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
            for name, raw in self.files.items()]}
        self.json('ingress-application-tracked.json', tracked)
        self.ext = {'schema_version': 1, 'source_archive_commit': self.source_commit,
                    'released_commit': self.release_commit, 'source_tree': self.tree,
                    'base_ledger_sha256': M.digest(self.record / 'service-sources.json'),
                    'images': {role: {'image_id': 'sha256:' + char * 64, 'base_images': {base: pinned}}
                               for role, char, base, pinned in (
                                   ('api', '1', 'python:3.12-slim', 'python@sha256:' + '4' * 64),
                                   ('portal', '2', 'node:22-alpine', 'node@sha256:' + '5' * 64))},
                    'caddy': {'image_id': 'sha256:' + '3' * 64,
                              'immutable_source': '/mnt/storage/configs/atlas/deployments/repairs/maintenance-access-fixture/source',
                              'binds': {'/etc/caddy': {'subdirectory': 'infra/caddy', 'rw': False},
                                        '/srv': {'subdirectory': 'infra/caddy/site', 'rw': False}}},
                    'authority': {'unit_path': '/etc/systemd/system/atlas-maintenance-control.service',
                                  'socket': '/run/atlas-maintenance-control/control.sock',
                                  'socket_uid': 0, 'socket_gid': 20000, 'socket_mode': '0660',
                                  'parent_mode': '0750', 'allowed_peer_uid': 999}}
        self.json('ingress-runtime-extension.json', self.ext)
        for role, image in self.ext['images'].items():
            raw = self.files['apps/' + role + '/Dockerfile']
            for old, new in image['base_images'].items():
                raw = raw.replace(('FROM ' + old).encode(), ('FROM ' + new).encode())
            (self.record / ('ingress-' + role + '-build.Dockerfile')).write_bytes(raw)
        unit = self.files['systemd/atlas-maintenance-control.service'].decode().replace(
            '/opt/project-atlas-v1-main', self.ext['caddy']['immutable_source']).replace(
                '/usr/bin/python3 -B -m', '/usr/bin/python3 -P -B -m')
        (self.record / 'maintenance-authority.service').write_text(unit)
        self.gate = {'schema_version': 1, 'event': 'push', 'head_sha': self.release_commit, 'source_tree': self.tree,
                     'workflow_path': '.github/workflows/release-gate.yml', 'run_id': 123, 'run_attempt': 1,
                     'conclusion': 'success', 'jobs': {name: 'success' for name in
                     ('Release Contracts', 'API', 'Portal', 'Core Python', 'Sports', 'release-gate')}}
        self.json('ingress-release-gate.json', self.gate)
        with (self.record / 'images.tsv').open('a') as stream:
            for role, image in {**self.ext['images'], 'caddy': self.ext['caddy']}.items():
                stream.write('ingress|stack/ingress.yml|atlas-ingress|' + role + '|/atlas-' + role + '|tag|' + image['image_id'] + '\n')
        values = M.metadata(self.record)
        values.update(E.MARKERS)
        values.update(source_claim=E.SOURCE_CLAIM, ingress_extension_commit=self.release_commit, ingress_extension_tree=self.tree)
        self.fixture.write_metadata(self.record, values)
        M.seal(self.record)

    def json(self, name, value):
        (self.record / name).write_text(json.dumps(value))

    def archive(self, commit=None):
        with tarfile.open(self.record / 'ingress-application-source.tar.gz', 'w:gz',
                          format=tarfile.PAX_FORMAT, pax_headers={'comment': commit or self.source_commit}) as archive:
            for name, raw in self.files.items():
                item = tarfile.TarInfo(name)
                item.mode, item.size = 0o644, len(raw)
                archive.addfile(item, io.BytesIO(raw))

    def reject(self):
        M.seal(self.record)
        with self.assertRaises((ValueError, KeyError, TypeError)):
            M.check_record(self.record)

    def test_valid_extension_keeps_base_ledger_and_sports_evidence(self):
        ledger, _, _ = M.check_record(self.record)
        self.assertEqual(set(ledger['ingress']['overrides']), {'sports-writer'})
        self.assertEqual(ledger['scheduler']['source_commit'], self.fixture.old)

    def test_every_required_supplement_is_mandatory(self):
        for name in E.SUPPLEMENTS:
            with self.subTest(name=name):
                file = self.record / name
                raw = file.read_bytes()
                file.unlink()
                self.reject()
                file.write_bytes(raw)
        M.seal(self.record)

    def test_downgrade_with_extension_files_refuses(self):
        values = M.metadata(self.record)
        values.update(M.MARKERS)
        values['source_claim'] = M.SOURCE_CLAIM
        self.fixture.write_metadata(self.record, values)
        self.reject()

    def test_partial_markers_refuse(self):
        values = M.metadata(self.record)
        values['requires_mixed_runtime_contract'] = '1'
        self.fixture.write_metadata(self.record, values)
        self.reject()

    def test_unknown_extension_schema_and_fields_refuse(self):
        for change in ({'schema_version': 9}, {'unreviewed': True}):
            with self.subTest(change=change):
                self.json('ingress-runtime-extension.json', {**self.ext, **change})
                self.reject()

    def test_resealed_archive_source_change_refuses(self):
        self.files['atlas/maintenance_control_server.py'] = b'changed=True\n'
        self.archive()
        self.reject()

    def test_wrong_archive_commit_refuses(self):
        self.archive('f' * 40)
        self.reject()

    def test_relabelled_tree_refuses_even_when_metadata_and_tracked_match(self):
        wrong = '0' * 40
        self.ext['source_tree'] = wrong
        self.json('ingress-runtime-extension.json', self.ext)
        tracked = json.loads(M.read(self.record / 'ingress-application-tracked.json'))
        tracked['tree'] = wrong
        self.json('ingress-application-tracked.json', tracked)
        values = M.metadata(self.record)
        values['ingress_extension_tree'] = wrong
        self.fixture.write_metadata(self.record, values)
        self.reject()

    def test_base_ledger_link_cannot_be_relabelled(self):
        self.ext['base_ledger_sha256'] = '0' * 64
        self.json('ingress-runtime-extension.json', self.ext)
        self.reject()

    def test_tracked_mode_or_coverage_changes_refuse(self):
        tracked = json.loads(M.read(self.record / 'ingress-application-tracked.json'))
        for change in ('mode', 'missing', 'duplicate'):
            with self.subTest(change=change):
                value = copy.deepcopy(tracked)
                if change == 'mode': value['files'][0]['mode'] = '100755'
                elif change == 'missing': value['files'].pop()
                else: value['files'].append(value['files'][0])
                self.json('ingress-application-tracked.json', value)
                self.reject()

    def test_modified_build_recipe_refuses(self):
        file = self.record / 'ingress-api-build.Dockerfile'
        file.write_bytes(file.read_bytes() + b'RUN unreviewed-command\n')
        self.reject()

    def test_unpinned_build_base_refuses(self):
        self.ext['images']['api']['base_images']['python:3.12-slim'] = 'python:latest'
        self.json('ingress-runtime-extension.json', self.ext)
        self.reject()

    def test_runtime_image_manifest_must_match(self):
        file = self.record / 'images.tsv'
        file.write_text(file.read_text().replace('sha256:' + '1' * 64, 'sha256:' + '9' * 64))
        self.reject()

    def test_caddy_writable_mount_or_traversal_refuses(self):
        for kind in ('rw', 'traversal'):
            with self.subTest(kind=kind):
                value = copy.deepcopy(self.ext)
                if kind == 'rw': value['caddy']['binds']['/srv']['rw'] = True
                else: value['caddy']['immutable_source'] += '/../escape'
                self.json('ingress-runtime-extension.json', value)
                self.reject()

    def test_host_authority_permission_widening_refuses(self):
        self.ext['authority']['socket_mode'] = '0666'
        self.json('ingress-runtime-extension.json', self.ext)
        self.reject()

    def test_authority_unit_missing_safe_path_or_wrong_source_refuses(self):
        file = self.record / 'maintenance-authority.service'
        raw = file.read_bytes()
        for changed in (raw.replace(b' -P -B ', b' -B '), raw.replace(b'maintenance-access-fixture', b'other')):
            file.write_bytes(changed)
            self.reject()

    def test_other_head_or_failed_release_gate_refuses(self):
        for change in ({'head_sha': '0' * 40}, {'conclusion': 'failure'}, {'jobs': {'release-gate': 'success'}}):
            with self.subTest(change=change):
                self.json('ingress-release-gate.json', {**self.gate, **change})
                self.reject()

    def test_live_refuses_before_any_docker_command(self):
        with patch.object(M, 'inspect') as inspect, patch.object(M.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Immutable Ingress source unavailable'):
                M.check_live(self.record)
            inspect.assert_not_called()
            run.assert_not_called()

    def test_restore_and_inheritance_refuse_without_destination_mutation(self):
        dest = self.fixture.root / 'destination'
        dest.mkdir()
        for operation in (lambda: M.inherit(self.record, dest), lambda: M.prepare_restore(self.record, dest)):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, 'pending recovery coordinator'):
                    operation()
                self.assertEqual(list(dest.iterdir()), [])

    def test_shell_detection_without_metadata_markers(self):
        folder = self.fixture.root / 'detection'
        folder.mkdir()
        (folder / 'metadata').write_text('type=baseline\n')
        (folder / 'ingress-runtime-extension.json').write_text('{}')
        script = ROOT / 'scripts/commands/deployment.sh'
        result = subprocess.run(['bash', '-c', 'source "$1"; atlas_deployment_is_mixed "$2"', 'test', str(script), str(folder)],
                                capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_schema2_update_preflight_refuses_even_full_scope(self):
        script = ROOT / 'scripts/commands/deployment.sh'
        for scope in ('all', 'ingress', 'core'):
            with self.subTest(scope=scope):
                result = subprocess.run(['bash', '-c',
                    'source "$1"; atlas_deployment_validate_update_inheritance "$2" "$3"',
                    'test', str(script), str(self.record), scope], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'pending component/recovery coordinator', result.stderr)

    def test_git_tree_oid_matches_git_with_directory_sorting_and_modes(self):
        folder = self.fixture.root / 'tree'
        folder.mkdir()
        subprocess.run(['git', 'init', '-q', str(folder)], check=True)
        files = {'a.c': b'one', 'a/z': b'two', 'script': b'three'}
        rows = {}
        for name, raw in files.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            executable = name == 'script'
            if executable: path.chmod(0o755)
            rows[name] = {'oid': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                          'executable': executable}
        subprocess.run(['git', '-C', str(folder), 'add', '.'], check=True)
        expected = subprocess.check_output(['git', '-C', str(folder), 'write-tree']).decode().strip()
        self.assertEqual(E.tree_oid(rows), expected)

    def test_tree_file_directory_collision_refuses(self):
        with self.assertRaises(ValueError):
            E.tree_oid({'a': {'oid': '0' * 40, 'executable': False}, 'a/b': {'oid': '0' * 40, 'executable': False}})


if __name__ == '__main__':
    unittest.main()
