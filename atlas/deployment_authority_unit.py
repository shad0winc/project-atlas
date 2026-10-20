"""Held no-replace authority unit installation and evidence-preserving rollback.

No systemctl, Docker or public CLI. Service lifecycle and component observations
remain delegated to the pending runtime adapter. Private tests supply fixtures.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat

from atlas.deployment_component_rollout import SURFACES, digest, observation, require
from atlas.deployment_immutable_generation import rename_no_replace
from atlas.deployment_publication_journal import identifier, read_file, safe_directory, sync_directory

UNIT_NAME = 'atlas-maintenance-control.service'


class AuthorityUnitArtifact:
    def __init__(self, proposal, expected_sha256, repair_id, *, unit_directory='/etc/systemd/system', checkpoint=None):
        self.proposal = Path(proposal)
        self.directory = Path(unit_directory)
        self.repair_id = identifier(repair_id)
        require(isinstance(expected_sha256, str) and len(expected_sha256) == 64
                and all(c in '0123456789abcdef' for c in expected_sha256), 'authority_unit_invalid_hash')
        self.sha256 = expected_sha256
        self.target = self.directory / UNIT_NAME
        self.staging = self.directory / ('.' + UNIT_NAME + '.' + self.repair_id + '.staged')
        self.retained = self.directory / ('.' + UNIT_NAME + '.' + self.repair_id + '.retained')
        self.checkpoint = checkpoint or (lambda point: None)
        self.target_fingerprint = digest({'schema_version': 1, 'unit_path': str(self.target), 'unit_sha256': self.sha256})
        self._proposal()

    def _proposal(self):
        safe_directory(self.proposal.parent)
        info = self.proposal.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and info.st_nlink == 1
                and not info.st_mode & 0o022, 'authority_unit_proposal_unavailable')
        raw = read_file(self.proposal, limit=65536)
        require(hashlib.sha256(raw).hexdigest() == self.sha256, 'authority_unit_proposal_changed')
        return raw

    @staticmethod
    def _identity(info):
        return {'device': info.st_dev, 'inode': info.st_ino, 'bytes': info.st_size,
                'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode), 'links': info.st_nlink}

    def _file(self, path, *, flush=False):
        safe_directory(self.directory)
        directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            opened_directory = os.fstat(directory_fd)
            current_directory = self.directory.lstat()
            require((opened_directory.st_dev, opened_directory.st_ino) ==
                    (current_directory.st_dev, current_directory.st_ino), 'authority_unit_directory_changed')
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
            try:
                before = os.fstat(fd)
                require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                        and (before.st_uid, before.st_gid) == (os.geteuid(), os.getegid())
                        and stat.S_IMODE(before.st_mode) == 0o644 and before.st_size <= 65536,
                        'authority_unit_file_metadata_differs')
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    raw = stream.read(65537)
                require(hashlib.sha256(raw).hexdigest() == self.sha256, 'authority_unit_file_bytes_differ')
                if flush: os.fsync(fd)
                after = os.fstat(fd)
                visible = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
                signature = lambda item: (self._identity(item), item.st_mtime_ns, item.st_ctime_ns)
                require(signature(before) == signature(after) == signature(visible), 'authority_unit_file_changed')
                return self._identity(after)
            finally:
                os.close(fd)
        finally:
            os.close(directory_fd)

    def inspect(self):
        self._proposal();safe_directory(self.directory)
        present = [(kind, path) for kind, path in (('staged', self.staging), ('published', self.target), ('retained', self.retained))
                   if path.exists() or path.is_symlink()]
        require(len(present) == 1, 'authority_unit_namespace_ambiguous')
        namespace, path = present[0]
        identity = self._file(path)
        return {'namespace': namespace, 'identity': identity, 'unit_sha256': self.sha256}

    def prepare(self, *, held_guard):
        require(held_guard() is True, 'authority_unit_hold_unproven')
        raw = self._proposal();safe_directory(self.directory)
        require(not self.target.exists() and not self.target.is_symlink()
                and not self.retained.exists() and not self.retained.is_symlink(), 'authority_unit_namespace_already_transitioned')
        if self.staging.exists() or self.staging.is_symlink():
            self._file(self.staging, flush=True)
        else:
            fd = os.open(self.staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                self.checkpoint('unit-staging-created')
                with os.fdopen(fd, 'wb', closefd=False) as stream:
                    stream.write(raw);stream.flush();os.fchmod(fd, 0o644);os.fsync(fd)
                self.checkpoint('unit-staging-file-durable')
            finally:
                os.close(fd)
        sync_directory(self.directory)
        require(held_guard() is True, 'authority_unit_hold_changed')
        self.checkpoint('unit-staging-durable')
        return self.inspect()

    def publish(self, *, held_guard):
        require(held_guard() is True, 'authority_unit_hold_unproven')
        state = self.inspect()
        require(state['namespace'] in ('staged', 'published'), 'authority_unit_retained_requires_new_plan')
        if state['namespace'] == 'staged':
            require(held_guard() is True, 'authority_unit_hold_changed')
            self.checkpoint('before-unit-publish-rename')
            rename_no_replace(self.staging, self.target)
            self.checkpoint('unit-publish-renamed')
        self._file(self.target, flush=True);sync_directory(self.directory)
        require(held_guard() is True, 'authority_unit_hold_changed')
        self.checkpoint('unit-publish-durable')
        return self.inspect()

    def retain(self, *, held_guard, inactive_guard):
        require(held_guard() is True and inactive_guard() is True, 'authority_unit_inactive_context_unproven')
        state = self.inspect()
        require(state['namespace'] in ('published', 'retained'), 'authority_unit_not_published')
        if state['namespace'] == 'published':
            require(held_guard() is True and inactive_guard() is True, 'authority_unit_inactive_context_changed')
            self.checkpoint('before-unit-retain-rename')
            rename_no_replace(self.target, self.retained)
            self.checkpoint('unit-retain-renamed')
        self._file(self.retained, flush=True);sync_directory(self.directory)
        require(held_guard() is True and inactive_guard() is True, 'authority_unit_inactive_context_changed')
        self.checkpoint('unit-retained-durable')
        return self.inspect()

    def observe(self):
        state = self.inspect()
        if state['namespace'] != 'published': return {'fingerprint': 'absent', 'identity': 'absent'}
        return {'fingerprint': self.target_fingerprint,
                'identity': digest({'unit': state['identity'], 'unit_sha256': self.sha256})}


class AuthorityUnitRolloutAdapter:
    """Inner runtime adapter for GenerationRolloutAdapter; service/Docker remain delegated."""
    def __init__(self, unit, runtime_adapter, *, held_guard):
        self.unit, self.runtime, self.held_guard = unit, runtime_adapter, held_guard
        require(all(callable(getattr(runtime_adapter, name, None)) for name in
                    ('observe', 'apply', 'rollback', 'verify', 'confirm', 'source_inactive', 'authority_inactive')),
                'authority_runtime_adapter_incomplete')
        unit.inspect()

    def _held(self):require(self.held_guard() is True, 'authority_unit_adapter_hold_unproven')
    def _name(self, name):require(name in SURFACES[1:], 'authority_unit_adapter_unknown_surface')

    def observe(self, name):
        self._name(name);self._held()
        result = self.unit.observe() if name == 'authority-unit' else observation(self.runtime.observe(name))
        self._held();return result

    def apply(self, name):
        self._name(name);self._held()
        if name == 'authority-unit': self.unit.publish(held_guard=self.held_guard)
        else: self.runtime.apply(name)
        self._held()

    def rollback(self, name):
        self._name(name);self._held()
        if name == 'authority-unit':
            self.unit.retain(held_guard=self.held_guard, inactive_guard=self.runtime.authority_inactive)
        else: self.runtime.rollback(name)
        self._held()

    def confirm(self, name, mode, expected):
        self._name(name);self._held();observation(expected)
        require(mode in ('apply', 'rollback') and self.observe(name) == expected, 'authority_unit_confirmation_changed')
        if name == 'authority-unit':
            state = self.unit.inspect()
            require(state['namespace'] == ('published' if mode == 'apply' else 'retained'), 'authority_unit_confirmation_namespace_differs')
            if mode == 'apply': self.unit.publish(held_guard=self.held_guard)
            else:
                self.unit.retain(held_guard=self.held_guard, inactive_guard=self.runtime.authority_inactive)
                # The lifecycle adapter reloads systemd only after the unit's
                # evidence-preserving rename is durable. Resume repeats this
                # confirmation if interrupted before the journal completion.
                retained = getattr(self.runtime, 'unit_retained', None)
                if retained is not None:
                    require(retained() is True, 'authority_unit_removal_not_confirmed')
        else:
            require(observation(self.runtime.confirm(name, mode, expected)) == expected, 'authority_runtime_confirmation_changed')
        self._held();result = self.observe(name)
        require(result == expected, 'authority_unit_confirmation_identity_changed')
        return result

    def verify(self, mode):
        self._held();require(mode in ('apply', 'rollback'), 'authority_unit_adapter_invalid_mode')
        state = self.unit.inspect()
        require(state['namespace'] == ('published' if mode == 'apply' else 'retained'), 'authority_unit_final_namespace_differs')
        require(self.runtime.verify(mode) is True, 'authority_runtime_final_verification_failed')
        if mode == 'rollback':require(self.runtime.authority_inactive() is True, 'authority_service_still_active')
        self._held();return True

    def source_inactive(self):
        self._held()
        result = self.unit.inspect()['namespace'] == 'retained' and self.runtime.source_inactive() is True
        self._held();return result
