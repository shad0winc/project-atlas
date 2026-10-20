"""Real private generation I/O, no-replace transitions and abrupt-exit holds."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import signal
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from atlas.deployment_immutable_generation import ImmutableGeneration, tree_oid
from atlas.maintenance_control import MaintenanceControlError


def sha(raw): return hashlib.sha256(raw).hexdigest()


class ImmutableGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ('deployments', 'deployments/repairs', 'evidence', 'maintenance', 'deployments/update.lock'):
            (self.root / name).mkdir(mode=0o700)
        self.boundary = {self.root / 'maintenance/enabled': b'held\n', self.root / 'deployments/current': b'baseline\n',
                         self.root / 'deployments/update.lock/owner': b'deployment_id=original-failed\n'}
        for path, raw in self.boundary.items(): path.write_bytes(raw)
        self.inodes = {path: path.stat().st_ino for path in self.boundary}
        self.archive = self.root / 'evidence/source.tar.gz'
        self.commit = 'a' * 40
        self.files = {'atlas/main.py': (b'pass\n', 0o644), 'scripts/run': (b'#!/bin/sh\n', 0o755),
                      'infra/caddy/site/maintenance.png': (b'png-fixture', 0o644)}
        self.write_archive()
        self.tree = tree_oid({name: {'oid': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                                    'executable': bool(mode & 0o111)} for name, (raw, mode) in self.files.items()})
        self.generation = self.make()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for parent, dirs, files in os.walk(self.root):
            path = Path(parent)
            if not path.is_symlink(): path.chmod(0o700)
        for path, raw in self.boundary.items():
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(path.stat().st_ino, self.inodes[path])
        self.temp.cleanup()

    def write_archive(self, extra=None, commit=None):
        with tarfile.open(self.archive, 'w:gz', format=tarfile.PAX_FORMAT, pax_headers={'comment': commit or self.commit}) as archive:
            for name, (raw, mode) in self.files.items():
                member = tarfile.TarInfo(name);member.mode = mode;member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))
            if extra is not None: archive.addfile(extra, io.BytesIO(b'') if extra.isfile() else None)

    def make(self, repair='private-generation', *, expected_sha=None, commit=None, tree=None):
        return ImmutableGeneration(self.root, repair, self.archive, expected_sha or sha(self.archive.read_bytes()),
                                   commit or self.commit, tree or self.tree)

    def held(self): return all(path.read_bytes() == raw for path, raw in self.boundary.items())

    def test_prepare_only_stages_exact_immutable_tree(self):
        stage = self.generation.prepare()
        result = self.generation.inspect()
        self.assertEqual(result['namespace'], 'staged')
        self.assertFalse(result['deployment_or_acceptance_proven'])
        self.assertFalse(self.generation.target.exists())
        for name, (raw, mode) in self.files.items():
            path = stage / name
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o555 if mode & 0o111 else 0o444)
        self.assertEqual(stat.S_IMODE(stage.stat().st_mode), 0o555)
        inode = stage.stat().st_ino
        self.assertEqual(self.generation.prepare().stat().st_ino, inode)

    def test_publish_and_retain_are_idempotent_without_deleting_evidence(self):
        stage = self.generation.prepare();inode = stage.stat().st_ino
        self.assertEqual(self.generation.publish(held_guard=self.held)['namespace'], 'published')
        self.assertEqual(self.generation.target.stat().st_ino, inode)
        self.assertEqual(self.generation.publish(held_guard=self.held)['namespace'], 'published')
        self.assertEqual(self.generation.retain(held_guard=self.held, inactive_guard=lambda: True)['namespace'], 'retained')
        self.assertEqual(self.generation.retained.stat().st_ino, inode)
        self.assertEqual(self.generation.retain(held_guard=self.held, inactive_guard=lambda: True)['namespace'], 'retained')
        self.assertTrue(self.generation.marker.is_file())
        with self.assertRaises(MaintenanceControlError): self.generation.publish(held_guard=self.held)

    def test_missing_held_or_inactive_guard_refuses_namespace_change(self):
        self.generation.prepare()
        with self.assertRaises(MaintenanceControlError): self.generation.publish(held_guard=lambda: False)
        self.generation.publish(held_guard=self.held)
        with self.assertRaises(MaintenanceControlError): self.generation.retain(held_guard=self.held, inactive_guard=lambda: False)
        self.assertTrue(self.generation.target.is_dir())

    def test_archive_checksum_commit_or_tree_mismatch_refuses_before_staging(self):
        for generation in (self.make(expected_sha='0' * 64), self.make(commit='b' * 40), self.make(tree='c' * 40)):
            with self.subTest(generation=generation), self.assertRaises(MaintenanceControlError): generation.prepare()
        self.assertFalse(self.generation.parent.exists())

    def test_traversal_symlink_hardlink_and_special_members_refuse(self):
        for name, kind in (('../escape', tarfile.REGTYPE), ('link', tarfile.SYMTYPE), ('hard', tarfile.LNKTYPE), ('pipe', tarfile.FIFOTYPE)):
            with self.subTest(name=name):
                member = tarfile.TarInfo(name);member.type = kind;member.linkname = 'atlas/main.py'
                self.write_archive(extra=member)
                with self.assertRaises(MaintenanceControlError): self.make().prepare()
                self.assertFalse(self.generation.parent.exists())

    def test_duplicate_or_untracked_empty_directory_refuses(self):
        for name, kind in (('atlas/main.py', tarfile.REGTYPE), ('foreign-empty', tarfile.DIRTYPE)):
            member = tarfile.TarInfo(name);member.type = kind
            self.write_archive(extra=member)
            with self.assertRaises(MaintenanceControlError): self.make().prepare()

    def test_foreign_or_symlink_repair_parent_refuses(self):
        self.generation.parent.mkdir()
        (self.generation.parent / 'foreign').write_bytes(b'retain')
        with self.assertRaises(MaintenanceControlError): self.generation.prepare()
        self.assertEqual((self.generation.parent / 'foreign').read_bytes(), b'retain')
        (self.generation.parent / 'foreign').unlink();self.generation.parent.rmdir()
        self.generation.parent.symlink_to(self.root / 'evidence', target_is_directory=True)
        with self.assertRaises(MaintenanceControlError): self.generation.prepare()
        self.assertEqual(set(path.name for path in (self.root / 'evidence').iterdir()), {'source.tar.gz'})

    def test_changed_source_mode_bytes_or_extra_file_refuses(self):
        stage = self.generation.prepare()
        file = stage / 'atlas/main.py'
        file.chmod(0o644)
        with self.assertRaises(MaintenanceControlError): self.generation.inspect()
        file.write_bytes(b'evil\n');file.chmod(0o444)
        with self.assertRaises(MaintenanceControlError): self.generation.inspect()
        file.chmod(0o644);file.write_bytes(b'pass\n');file.chmod(0o444)
        stage.chmod(0o755);(stage / 'extra').write_bytes(b'extra');(stage / 'extra').chmod(0o444);stage.chmod(0o555)
        with self.assertRaises(MaintenanceControlError): self.generation.inspect()

    def test_marker_change_or_partial_preparation_is_not_replaced(self):
        self.generation.prepare()
        self.generation.marker.write_bytes(b'changed')
        with self.assertRaises((MaintenanceControlError, ValueError)): self.generation.prepare()
        self.assertEqual(self.generation.marker.read_bytes(), b'changed')
        other = self.make('partial');other.parent.mkdir();other.staging.mkdir()
        (other.staging / 'partial').write_bytes(b'keep')
        with self.assertRaises(MaintenanceControlError): other.prepare()
        self.assertEqual((other.staging / 'partial').read_bytes(), b'keep')

    def test_foreign_empty_directory_is_never_overwritten_by_publish_or_retain(self):
        self.generation.prepare()
        def stop_publish(phase):
            if phase == 'before-source-rename': self.generation.target.mkdir()
        self.generation.checkpoint = stop_publish
        with self.assertRaises(OSError): self.generation.publish(held_guard=self.held)
        self.assertTrue(self.generation.staging.is_dir());self.generation.target.rmdir()
        self.generation.checkpoint = lambda phase: None
        self.generation.publish(held_guard=self.held)
        def stop_retain(phase):
            if phase == 'before-retain-rename': self.generation.retained.mkdir()
        self.generation.checkpoint = stop_retain
        with self.assertRaises(OSError): self.generation.retain(held_guard=self.held, inactive_guard=lambda: True)
        self.assertTrue(self.generation.target.is_dir());self.assertTrue(self.generation.retained.is_dir())

    def test_marker_fsync_uncertainty_reflushes_visible_exact_evidence(self):
        from atlas import deployment_immutable_generation as generation_module
        original_create = generation_module.create_once
        def uncertain(path, raw):
            original_create(path, raw)
            raise OSError('fixture marker durability uncertainty')
        with patch.object(generation_module, 'create_once', side_effect=uncertain), self.assertRaises(OSError):
            self.generation.prepare()
        inode = self.generation.marker.stat().st_ino
        original_fsync = os.fsync
        flushed = []
        def observe(fd):
            if os.fstat(fd).st_ino == inode: flushed.append(True)
            return original_fsync(fd)
        with patch.object(generation_module.os, 'fsync', side_effect=observe):
            self.generation.prepare()
        self.assertTrue(flushed)
        self.assertEqual(self.generation.inspect()['namespace'], 'staged')

    def test_large_asset_is_streamed(self):
        self.files['infra/caddy/site/maintenance.png'] = (b'x' * (2 * 1024 * 1024), 0o644)
        self.write_archive()
        catalog = {name: {'oid': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                          'executable': bool(mode & 0o111)} for name, (raw, mode) in self.files.items()}
        generation = self.make(tree=tree_oid(catalog));generation.prepare()
        self.assertEqual(generation.inspect()['file_count'], 3)

    def kill(self, generation, phase, action):
        pid = os.fork()
        if pid == 0:
            generation.checkpoint = lambda step: os.kill(os.getpid(), signal.SIGKILL) if step == phase else None
            try:
                if action == 'prepare': generation.prepare()
                elif action == 'publish': generation.publish(held_guard=self.held)
                else: generation.retain(held_guard=self.held, inactive_guard=lambda: True)
            finally: os._exit(98)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFSIGNALED(status), (phase, status))
        self.assertTrue(self.held())

    def test_kill_during_incomplete_preparation_retains_partial_source_and_refuses(self):
        for index, phase in enumerate(('staging-created', 'file-durable', 'staging-tree-durable')):
            with self.subTest(phase=phase):
                generation = self.make('partial-' + str(index));self.kill(generation, phase, 'prepare')
                self.assertTrue(generation.staging.is_dir());self.assertFalse(generation.target.exists())
                with self.assertRaises((MaintenanceControlError, OSError)): generation.prepare()
                with self.assertRaises((MaintenanceControlError, OSError)): generation.publish(held_guard=self.held)

    def test_kill_after_complete_staging_can_reflush_exact_tree(self):
        for index, phase in enumerate(('staging-marker-durable', 'staging-durable')):
            with self.subTest(phase=phase):
                generation = self.make('complete-' + str(index));self.kill(generation, phase, 'prepare')
                self.assertTrue(generation.prepare().is_dir())
                self.assertEqual(generation.inspect()['namespace'], 'staged')

    def test_kill_at_each_namespace_boundary_can_resume_without_replacement(self):
        phases = [('publish', phase) for phase in ('before-source-rename', 'source-renamed', 'source-namespace-durable')]
        phases += [('retain', phase) for phase in ('before-retain-rename', 'source-retained-renamed', 'retained-namespace-durable')]
        for index, (action, phase) in enumerate(phases):
            with self.subTest(phase=phase):
                generation = self.make('namespace-' + str(index));generation.prepare()
                inode = generation.staging.stat().st_ino
                if action == 'retain': generation.publish(held_guard=self.held)
                self.kill(generation, phase, action)
                result = generation.publish(held_guard=self.held) if action == 'publish' else generation.retain(held_guard=self.held, inactive_guard=lambda: True)
                self.assertEqual(Path(result['source_path']).stat().st_ino, inode)
                self.assertEqual(result['namespace'], 'published' if action == 'publish' else 'retained')


if __name__ == '__main__': unittest.main()
