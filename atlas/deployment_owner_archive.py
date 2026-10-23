"""Host-only owner-directory archival mechanism; admission policy is external.

There is deliberately no CLI, socket operation, marker completion or maintenance
disable. A promoted host driver must supply and revalidate admission evidence.
The preservation plan is identity evidence, never a release permit.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from atlas.deployment_publication_journal import (
    create_once, encoded, identifier, read_file, safe_directory, sync_directory,
)
from atlas.maintenance_control import MaintenanceAuthority, MaintenanceControlError


def _rename_directory(source, destination):
    """Linux no-replace rename only: never copy, overwrite or delete an owner."""
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, 'renameat2', None)
    if rename is None:
        raise MaintenanceControlError('owner_archive_noreplace_unavailable')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    source_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    target_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(source_fd).st_dev != os.fstat(target_fd).st_dev:
            raise MaintenanceControlError('owner_archive_requires_same_filesystem')
        if rename(source_fd, os.fsencode(source.name), target_fd, os.fsencode(destination.name), 1):
            value = ctypes.get_errno()
            if value == errno.EEXIST:
                raise MaintenanceControlError('owner_archive_target_exists')
            raise MaintenanceControlError('owner_archive_rename_failed')
    finally:
        os.close(target_fd)
        os.close(source_fd)


class OwnerArchive(MaintenanceAuthority):
    """Archive exactly one sealed owner under a verified inherited flock.

    ``admit`` is a mandatory trusted host-driver verifier, not user input. It
    receives the exact admission object and phase and must raise on refusal.
    This mechanism hashes that evidence but cannot establish remote CI, browser
    identity, private receipt freshness, or the driver's own source provenance.
    A driver implementing those checks is required before production use.
    """

    def __init__(self, runtime_root, original_owner, inherited_fd, **kwargs):
        super().__init__(runtime_root, **kwargs)
        self.original_owner = identifier(original_owner)
        if type(inherited_fd) is not int or inherited_fd < 3:
            raise MaintenanceControlError('invalid_transaction_context')
        self.inherited_fd = inherited_fd

    @contextmanager
    def _exclusion(self):
        # Unlike the original transaction helper, exclusion remains inspectable
        # after the owner moves. Owner identity is checked separately below.
        borrowed = probe = None
        try:
            self._directories()
            borrowed = os.dup(self.inherited_fd)
            info = os.fstat(borrowed)
            path = self.lock.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != os.geteuid() or info.st_mode & 0o022
                    or not stat.S_ISREG(path.st_mode) or self.lock.resolve(strict=True) != self.lock
                    or (info.st_dev, info.st_ino) != (path.st_dev, path.st_ino)):
                raise MaintenanceControlError('owner_archive_exclusion_unavailable')
            probe = os.open(self.lock, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            if (os.fstat(probe).st_dev, os.fstat(probe).st_ino) != (info.st_dev, info.st_ino):
                raise MaintenanceControlError('owner_archive_exclusion_unavailable')
            try:
                fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise MaintenanceControlError('exclusive_parent_not_proven')
            try:
                fcntl.flock(borrowed, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MaintenanceControlError('exclusive_parent_not_proven') from None
            yield
        except OSError:
            raise MaintenanceControlError('owner_archive_io_uncertain') from None
        finally:
            # Never unlock the shared open description owned by the parent.
            for fd in (probe, borrowed):
                if fd is not None:
                    os.close(fd)

    def _inventory(self, path):
        before = safe_directory(path)
        if {item.name for item in path.iterdir()} != {'owner'}:
            raise MaintenanceControlError('owner_archive_inventory_changed')
        raw = read_file(path / 'owner', limit=4096)
        info = (path / 'owner').lstat()
        if info.st_uid != os.geteuid():
            raise MaintenanceControlError('owner_archive_identity_changed')
        identities = [line for line in raw.decode('ascii').splitlines() if line.startswith('deployment_id=')]
        if identities != ['deployment_id=' + self.original_owner]:
            raise MaintenanceControlError('owner_archive_identity_changed')
        after = safe_directory(path)
        fields = lambda value: (value.st_dev, value.st_ino, value.st_uid, value.st_gid,
                                value.st_mode, value.st_mtime_ns, value.st_ctime_ns)
        if fields(before) != fields(after):
            raise MaintenanceControlError('owner_archive_inventory_changed')
        return {'directory': {'device': before.st_dev, 'inode': before.st_ino,
                    'uid': before.st_uid, 'gid': before.st_gid, 'mode': stat.S_IMODE(before.st_mode)},
                'files': {'owner': {'device': info.st_dev, 'inode': info.st_ino,
                    'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
                    'links': info.st_nlink, 'sha256': hashlib.sha256(raw).hexdigest()}}}

    def _context(self, publication, plan_sha256):
        identifier(publication)
        if not isinstance(plan_sha256, str) or re.fullmatch('[0-9a-f]{64}', plan_sha256) is None:
            raise MaintenanceControlError('owner_archive_plan_pin_invalid')
        parent = self.root / 'deployments/publication-journals'
        safe_directory(parent)
        folder = parent / publication
        safe_directory(folder)
        allowed = {'original-lock-owner', 'intent.json', 'record-staging', 'record-observed.json',
                   'held-boundary.json', 'private-attempts', 'owner-preservation.json',
                   'owner-archive-intent.json', 'owner-archive-completed.json', 'original-update.lock'}
        if not {path.name for path in folder.iterdir()} <= allowed:
            raise MaintenanceControlError('owner_archive_journal_inventory_changed')
        raw = read_file(folder / 'owner-preservation.json', limit=65536)
        if hashlib.sha256(raw).hexdigest() != plan_sha256:
            raise MaintenanceControlError('owner_archive_plan_changed')
        plan = json.loads(raw)
        relative = 'deployments/publication-journals/' + publication + '/original-update.lock'
        if (plan.get('schema_version') != 1 or plan.get('publication_id') != publication
                or plan.get('scope') != 'owner-preservation-preparation-only'
                or plan.get('archive_relative') != relative
                or plan.get('archive_method_required') != 'same-filesystem-whole-directory-rename-with-parent-fsync'
                or plan.get('owner_release_permitted') is not False
                or plan.get('original_owner', {}).get('deployment_id') != self.original_owner):
            raise MaintenanceControlError('owner_archive_plan_invalid')
        # Keep maintenance and the exact publication fence closed in every phase.
        if self.pending.exists() or self.pending.is_symlink():
            raise MaintenanceControlError('owner_archive_control_transition_pending')
        flag = read_file(self.flag, limit=4096)
        if (read_file(folder / 'intent.json') != plan['intent_sha256']
                or read_file(folder / 'held-boundary.json') != plan['held_boundary_sha256']
                or read_file(self.root / 'deployments/current') != plan['current_sha256']
                or read_file(self.root / 'deployments/current', limit=256) != (publication + '\n').encode()
                or read_file(self.publication_pending, limit=4096) != encoded({
                    'publication_id': publication, 'intent_sha256': plan['intent_sha256']})):
            raise MaintenanceControlError('owner_archive_context_changed')
        archive = self.root / relative
        live_exists = os.path.lexists(self.recovery_lock)
        archive_exists = os.path.lexists(archive)
        if live_exists == archive_exists:
            raise MaintenanceControlError('owner_archive_ambiguous_location')
        location = self.recovery_lock if live_exists else archive
        if self._inventory(location) != plan['original_lock_inventory']:
            raise MaintenanceControlError('owner_archive_identity_changed')
        if read_file(folder / 'original-lock-owner', limit=4096) != read_file(location / 'owner', limit=4096):
            raise MaintenanceControlError('owner_archive_owner_copy_changed')
        return folder, plan, archive, live_exists, hashlib.sha256(flag).hexdigest()

    def _intent(self, publication, plan_sha256, admission, flag_sha256):
        # No booleans in this record purport to grant release or public proof.
        if not isinstance(admission, dict) or not admission:
            raise MaintenanceControlError('owner_archive_admission_required')
        if len(encoded(admission)) > 65536:
            raise MaintenanceControlError('owner_archive_admission_too_large')
        return {'schema_version': 1, 'scope': 'owner-directory-archive-only',
                'publication_id': publication, 'original_owner': self.original_owner,
                'preservation_plan_sha256': plan_sha256, 'admission': admission,
                'maintenance_flag_sha256': flag_sha256,
                'publication_marker_completion_performed': False,
                'ordinary_reopening_permitted': False}

    def inspect(self, publication, plan_sha256):
        """Read only, including after interruption; never refresh admission."""
        with self._exclusion():
            folder, plan, archive, live, flag = self._context(publication, plan_sha256)
            intent_path = folder / 'owner-archive-intent.json'
            done_path = folder / 'owner-archive-completed.json'
            intent = None
            if os.path.lexists(intent_path):
                raw = read_file(intent_path, limit=131072)
                intent = json.loads(raw)
                expected = self._intent(publication, plan_sha256, intent['admission'], flag)
                if raw != encoded(expected):
                    raise MaintenanceControlError('owner_archive_intent_conflict')
            if not live and intent is None:
                raise MaintenanceControlError('owner_archive_unjournaled_move')
            completed = os.path.lexists(done_path)
            if completed:
                if live or intent is None or read_file(done_path, limit=4096) != encoded({
                        'schema_version': 1, 'archive_intent_sha256': hashlib.sha256(encoded(intent)).hexdigest(),
                        'owner_inventory': plan['original_lock_inventory'],
                        'maintenance_preserved': True, 'publication_marker_preserved': True}):
                    raise MaintenanceControlError('owner_archive_completion_conflict')
            return {'phase': 'archived' if completed else 'moved-needs-parent-sync' if not live
                    else 'intent-durable-owner-live' if intent else 'owner-live',
                    'maintenance_enabled': True, 'publication_marker_preserved': True,
                    'ordinary_reopening_permitted': False}

    def archive(self, publication, plan_sha256, admission, *, admit):
        """Explicit host operation. Retry requires the same admission and verifier.

        For a moved directory the verifier must support that phase without
        replaying an owner-live collector or treating old evidence as fresh.
        A refusal leaves the owner wherever it is, maintenance and marker intact.
        """
        if not callable(admit):
            raise MaintenanceControlError('owner_archive_admission_verifier_required')
        # Freeze caller-owned mutable input before invoking trusted callbacks.
        admission = json.loads(encoded(admission))
        with self._exclusion():
            state = self.inspect(publication, plan_sha256)
            folder, plan, target, live, flag = self._context(publication, plan_sha256)
            intent = self._intent(publication, plan_sha256, admission, flag)
            intent_path = folder / 'owner-archive-intent.json'
            if os.path.lexists(intent_path) and read_file(intent_path, limit=131072) != encoded(intent):
                raise MaintenanceControlError('owner_archive_intent_conflict')
            # Must revalidate on every retry, even if completion is visible.
            if admit(json.loads(encoded(admission)), state['phase']) is not None:
                raise MaintenanceControlError('owner_archive_admission_verifier_result_invalid')
            if not os.path.lexists(intent_path):
                create_once(intent_path, encoded(intent))
            # A failed previous flush may have left complete visible intent bytes.
            # Never move based on visibility alone, including on explicit retry.
            fd = os.open(intent_path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            sync_directory(folder)
            self.checkpoint('owner_archive_intent_durable')
            if admit(json.loads(encoded(admission)), state['phase']) is not None:
                raise MaintenanceControlError('owner_archive_admission_verifier_result_invalid')
            if self._context(publication, plan_sha256) != (folder, plan, target, live, flag):
                raise MaintenanceControlError('owner_archive_context_changed')
            if live:
                _rename_directory(self.recovery_lock, target)
                self.checkpoint('owner_archive_directory_moved')
            # A retry after a rename/fsync failure must flush both namespaces.
            sync_directory(target)
            sync_directory(target.parent)
            sync_directory(self.recovery_lock.parent)
            self.checkpoint('owner_archive_parents_durable')
            self._context(publication, plan_sha256)
            completed = {'schema_version': 1, 'archive_intent_sha256': hashlib.sha256(encoded(intent)).hexdigest(),
                         'owner_inventory': plan['original_lock_inventory'],
                         'maintenance_preserved': True, 'publication_marker_preserved': True}
            path = folder / 'owner-archive-completed.json'
            if os.path.lexists(path):
                if read_file(path, limit=4096) != encoded(completed):
                    raise MaintenanceControlError('owner_archive_completion_conflict')
            else:
                create_once(path, encoded(completed))
            # Explicitly retry the flush if a prior create left visible bytes.
            for item in (intent_path, path):
                fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            sync_directory(folder)
            self.checkpoint('owner_archive_completed_durable')
            return self.inspect(publication, plan_sha256)
