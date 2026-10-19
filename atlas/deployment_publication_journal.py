"""Durable host-only publication intent; no record/pointer or owner mutation.

The marker fences ordinary reopening before any finalizer mutation. A complete
intent can be inspected or retried while original current and ownership remain
exact. Partial or changed evidence requires host review; it is never overwritten.
This foundation neither accepts a runtime nor implements publication/release.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

from atlas.maintenance_control import MaintenanceControlError
from atlas.maintenance_transaction import TransactionMaintenanceAuthority


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def identifier(value):
    if not isinstance(value, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value) is None:
        raise MaintenanceControlError('invalid_publication_identity')
    return value


def safe_directory(path):
    info = path.lstat()
    if (not path.is_absolute() or path.resolve(strict=True) != path or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid() or info.st_mode & 0o022):
        raise MaintenanceControlError('publication_evidence_unavailable')
    return info


def read_file(path, *, limit=None):
    safe_directory(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_mode & 0o022
                or (limit is not None and before.st_size > limit)):
            raise MaintenanceControlError('publication_evidence_unavailable')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            value = stream.read(limit + 1) if limit is not None else hashlib.file_digest(stream, 'sha256').hexdigest()
            if limit is not None and len(value) > limit:
                raise MaintenanceControlError('publication_evidence_unavailable')
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise MaintenanceControlError('publication_evidence_changed')
        return value
    finally:
        os.close(fd)


def sync_directory(path):
    before = safe_directory(path)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise MaintenanceControlError('publication_evidence_changed')
        os.fsync(fd)
    finally:
        os.close(fd)


def create_once(path, raw):
    safe_directory(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw);stream.flush();os.fsync(fd)
    finally:
        os.close(fd)
    sync_directory(path.parent)


class PublicationIntentJournal(TransactionMaintenanceAuthority):
    """Use only under the exact original owner's inherited exclusive flock."""
    def _owner_fields(self, owner):
        info = (self.recovery_lock / 'owner').lstat()
        return {'deployment_id':self.identifier, 'directory_device':owner[0], 'directory_inode':owner[1],
            'file_device':info.st_dev, 'file_inode':info.st_ino, 'file_uid':info.st_uid,
            'file_gid':info.st_gid, 'file_mode':stat.S_IMODE(info.st_mode),
            'sha256':hashlib.sha256(owner[2]).hexdigest()}

    def _held(self):
        state = self.status()
        if state['state_uncertain'] or not self._present(self.flag) or self._present(self.pending):
            raise MaintenanceControlError('publication_maintenance_hold_unproven')

    def _paths(self, publication):
        identifier(publication)
        parent = self.root / 'deployments/publication-journals'
        return parent, parent / publication

    def _candidate(self, relative, expected_manifest):
        name = PurePosixPath(relative)
        if (name.is_absolute() or '..' in name.parts or str(name) != relative or len(name.parts) < 3
                or name.parts[:2] != ('deployments', 'repairs')):
            raise MaintenanceControlError('invalid_publication_candidate')
        candidate = self.root / relative
        safe_directory(candidate)
        manifest = read_file(candidate / 'MANIFEST.sha256', limit=1024 * 1024)
        if hashlib.sha256(manifest).hexdigest() != expected_manifest:
            raise MaintenanceControlError('publication_candidate_changed')
        pins = {}
        for line in manifest.decode('ascii').splitlines():
            match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9_.-]{0,127})', line)
            if match is None or match[2] in pins or match[2] == 'MANIFEST.sha256':
                raise MaintenanceControlError('invalid_publication_candidate_manifest')
            pins[match[2]] = match[1]
        if not {'metadata', 'status', 'core-source.tar.gz', 'images.tsv'} <= set(pins):
            raise MaintenanceControlError('incomplete_publication_candidate_manifest')
        if set(path.name for path in candidate.iterdir()) != set(pins) | {'MANIFEST.sha256'}:
            raise MaintenanceControlError('publication_candidate_inventory_changed')
        if any(read_file(candidate / name) != digest for name, digest in pins.items()):
            raise MaintenanceControlError('publication_candidate_changed')
        return pins

    def _journal_files(self, folder):
        safe_directory(folder)
        names = set(path.name for path in folder.iterdir())
        if not {'original-lock-owner', 'intent.json'} <= names or names - {
                'original-lock-owner', 'intent.json', 'record-staging', 'record-observed.json', 'held-boundary.json', 'private-attempts', 'owner-preservation.json'}:
            raise MaintenanceControlError('publication_incomplete_requires_host_review')

    def begin(self, *, publication_id, expected_current, candidate_relative, candidate_manifest, evidence):
        publication_id = identifier(publication_id);expected_current = identifier(expected_current)
        if publication_id in (expected_current, self.identifier) or not isinstance(evidence, dict):
            raise MaintenanceControlError('invalid_publication_intent')
        if not isinstance(candidate_manifest, str) or re.fullmatch(r'[0-9a-f]{64}', candidate_manifest) is None:
            raise MaintenanceControlError('invalid_publication_intent')
        with self._exclusive():
            self._held()
            owner = self._owner();owner_fields = self._owner_fields(owner)
            current = read_file(self.root / 'deployments/current', limit=256)
            if current != (expected_current + '\n').encode():
                raise MaintenanceControlError('publication_current_changed')
            candidate_pins = self._candidate(candidate_relative, candidate_manifest)
            required = {str(self.root / 'deployments/records' / name / file)
                        for name in (expected_current, self.identifier) for file in ('metadata', 'status')}
            if not required <= set(evidence) or len(evidence) > 4096:
                raise MaintenanceControlError('incomplete_publication_evidence')
            for name, digest in evidence.items():
                if not isinstance(name, str) or not Path(name).is_absolute() or not isinstance(digest, str):
                    raise MaintenanceControlError('invalid_publication_evidence')
                if read_file(Path(name)) != digest:
                    raise MaintenanceControlError('publication_protected_evidence_changed')
            intent = {'schema_version': 1, 'publication_id': publication_id,
                'original_owner': owner_fields,
                'old_current': expected_current, 'old_current_sha256': hashlib.sha256(current).hexdigest(),
                'candidate_relative': candidate_relative, 'candidate_manifest_sha256': candidate_manifest,
                'candidate_files': candidate_pins, 'protected_evidence': evidence,
                'scope': 'intent-only-no-acceptance-no-publication-no-owner-release'}
            raw = encoded(intent);digest = hashlib.sha256(raw).hexdigest()
            marker = encoded({'publication_id': publication_id, 'intent_sha256': digest})
            parent, folder = self._paths(publication_id)
            if self.publication_pending.exists() or self.publication_pending.is_symlink():
                if read_file(self.publication_pending, limit=4096) != marker:
                    raise MaintenanceControlError('publication_intent_conflict')
                self._journal_files(folder)
                if set(path.name for path in folder.iterdir()) != {'original-lock-owner','intent.json'}:
                    raise MaintenanceControlError('publication_already_started_requires_resume')
                if read_file(folder / 'intent.json', limit=4 * 1024 * 1024) != raw or read_file(folder / 'original-lock-owner', limit=4096) != owner[2]:
                    raise MaintenanceControlError('publication_intent_conflict')
                # A previous fsync error may have left complete visible files.
                # Inspection is safe; success requires the caller's explicit retry
                # and a fresh flush of the immutable files and namespaces.
                for path in (self.publication_pending, folder / 'original-lock-owner', folder / 'intent.json'):
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                    try:os.fsync(fd)
                    finally:os.close(fd)
                for path in (folder, parent, parent.parent, self.directory):sync_directory(path)
                return digest
            # Marker precedes every durable intent artifact. Any interruption
            # leaves maintenance admission closed and retains the original owner.
            create_once(self.publication_pending, marker);self.checkpoint('publication_pending_durable')
            for path in (parent, folder):
                try:path.mkdir(mode=0o700)
                except FileExistsError:safe_directory(path)
                sync_directory(path.parent)
            if any(folder.iterdir()):
                raise MaintenanceControlError('publication_intent_conflict')
            create_once(folder / 'original-lock-owner', owner[2]);self.checkpoint('publication_owner_copy_durable')
            create_once(folder / 'intent.json', raw);self.checkpoint('publication_intent_durable')
            self._journal_files(folder)
            if (self._owner() != owner or self._owner_fields(owner) != owner_fields
                    or read_file(self.root / 'deployments/current', limit=256) != current):
                raise MaintenanceControlError('publication_context_changed')
            if self._candidate(candidate_relative, candidate_manifest) != candidate_pins or any(
                    read_file(Path(name)) != value for name, value in evidence.items()):
                raise MaintenanceControlError('publication_protected_evidence_changed')
            return digest

    def inspect(self, publication_id):
        return self._inspect(publication_id)

    def _inspect(self, publication_id, *, allow_published_current=False):
        """Return a checked intent, never infer acceptance from visible pointers."""
        with self._exclusive():
            self._held();parent, folder = self._paths(publication_id);self._journal_files(folder)
            raw = read_file(folder / 'intent.json', limit=4 * 1024 * 1024)
            intent = json.loads(raw)
            if intent.get('schema_version') != 1 or intent.get('publication_id') != publication_id:
                raise MaintenanceControlError('invalid_publication_journal')
            owner = self._owner();recorded = intent['original_owner']
            if recorded != self._owner_fields(owner):
                raise MaintenanceControlError('publication_original_owner_changed')
            if read_file(folder / 'original-lock-owner', limit=4096) != owner[2]:
                raise MaintenanceControlError('publication_original_owner_changed')
            marker = encoded({'publication_id':publication_id, 'intent_sha256':hashlib.sha256(raw).hexdigest()})
            if read_file(self.publication_pending, limit=4096) != marker:
                raise MaintenanceControlError('publication_intent_conflict')
            current = read_file(self.root / 'deployments/current', limit=256)
            allowed = {(intent['old_current'] + '\n').encode()}
            if allow_published_current:allowed.add((publication_id + '\n').encode())
            if current not in allowed:
                raise MaintenanceControlError('publication_pointer_moved_requires_review')
            if self._candidate(intent['candidate_relative'], intent['candidate_manifest_sha256']) != intent['candidate_files']:
                raise MaintenanceControlError('publication_candidate_changed')
            if any(read_file(Path(name)) != digest for name, digest in intent['protected_evidence'].items()):
                raise MaintenanceControlError('publication_protected_evidence_changed')
            return intent
