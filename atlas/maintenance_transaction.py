"""Host-only enable under a verified inherited transaction exclusion.

No socket operation, disable exception, publication, or recovery-lock release is
provided. Closing the borrowed descriptor must never unlock the parent's flock.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import stat
import uuid

from atlas.maintenance_control import MaintenanceAuthority, MaintenanceControlError


class TransactionMaintenanceAuthority(MaintenanceAuthority):
    def __init__(self, runtime_root: Path, identifier: str, inherited_fd: int, **kwargs):
        super().__init__(runtime_root, **kwargs)
        if (not isinstance(identifier, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', identifier) is None
            or type(inherited_fd) is not int or inherited_fd < 3):
            raise MaintenanceControlError('invalid_transaction_context')
        self.identifier = identifier
        self.inherited_fd = inherited_fd

    def _owner(self):
        self._directories()
        info = self.recovery_lock.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022
            or self.recovery_lock.resolve(strict=True) != self.recovery_lock):
            raise MaintenanceControlError('transaction_owner_unavailable')
        fd = os.open(self.recovery_lock / 'owner', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            owner = os.fstat(fd)
            if (not stat.S_ISREG(owner.st_mode) or owner.st_nlink != 1 or owner.st_uid != os.geteuid()
                or owner.st_mode & 0o022 or owner.st_size > 4096):
                raise MaintenanceControlError('transaction_owner_unavailable')
            raw = os.read(fd, 4097)
        finally:
            os.close(fd)
        try:
            identities = [line for line in raw.decode('ascii').splitlines() if line.startswith('deployment_id=')]
        except UnicodeError:
            raise MaintenanceControlError('transaction_owner_unavailable') from None
        if identities != ['deployment_id=' + self.identifier]:
            raise MaintenanceControlError('transaction_owner_mismatch')
        return info.st_dev, info.st_ino, raw

    @contextmanager
    def _exclusive(self):
        borrowed = probe = None
        try:
            before = self._owner()
            borrowed = os.dup(self.inherited_fd)
            info = os.fstat(borrowed)
            path_info = self.lock.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid()
                or (info.st_dev, info.st_ino) != (path_info.st_dev, path_info.st_ino)
                or not stat.S_ISREG(path_info.st_mode)):
                raise MaintenanceControlError('exclusion_unavailable')
            probe = os.open(self.lock, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            checked = os.fstat(probe)
            if (checked.st_dev, checked.st_ino) != (info.st_dev, info.st_ino):
                raise MaintenanceControlError('exclusion_unavailable')
            # A separate open description must be unable even to take a shared
            # lock. Otherwise no exclusive parent ownership has been proven.
            try:
                fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise MaintenanceControlError('exclusive_parent_not_proven')
            # Only the same open description can reacquire without contention.
            # An unrelated descriptor cannot borrow another process's ownership.
            try:
                fcntl.flock(borrowed, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MaintenanceControlError('exclusive_parent_not_proven') from None
            if self._owner() != before:
                raise MaintenanceControlError('transaction_owner_mismatch')
            yield
        except OSError:
            raise MaintenanceControlError('transaction_context_unavailable') from None
        finally:
            # Never LOCK_UN the inherited open description: parent still owns it.
            for fd in (probe, borrowed):
                if fd is not None:
                    os.close(fd)

    def change(self, enabled: bool, *, actor: str, source: str):
        if enabled is not True or source != 'cli':
            raise MaintenanceControlError('transaction_enable_only')
        return super().change(True, actor=actor, source='cli')

    def recover_hold(self, *, actor: str):
        raise MaintenanceControlError('transaction_enable_only')

    def verify_hold(self, *, actor: str):
        self._identity(actor, 'cli')
        with self._exclusive():
            state = self.status()
            if not state['enabled'] or state['transition_pending'] or state['state_uncertain']:
                raise MaintenanceControlError('maintenance_hold_not_proven')
            self._append_audit('verify_hold', actor, 'cli', uuid.uuid4().hex, 'completed')
            return state
