"""Narrow host maintenance authority; no deployment mutation or lock release.

Ingress and API integration MUST treat ``control-pending`` as maintenance.
That marker keeps every interrupted transition closed until explicit host repair.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import uuid
from collections.abc import Callable, Iterator


class MaintenanceControlError(RuntimeError):
    """A fixed public failure code, without filesystem/private exception text."""


class MaintenanceAuthority:
    def __init__(self, runtime_root: Path, *, checkpoint: Callable[[str], None] | None = None):
        self.root = Path(runtime_root)
        self.directory = self.root / 'maintenance'
        self.flag = self.directory / 'enabled'
        self.pending = self.directory / 'control-pending'
        self.publication_pending = self.directory / 'publication-pending'
        self.lock = self.root / 'deployment-scheduler.lock'
        self.recovery_lock = self.root / 'deployments/update.lock'
        self.audit = self.directory / 'control-audit.jsonl'
        self.checkpoint = checkpoint or (lambda phase: None)

    def _directories(self) -> None:
        if not self.root.is_absolute():
            raise MaintenanceControlError('state_unavailable')
        for directory in (self.root, self.directory, self.root / 'deployments'):
            try:
                if directory.resolve(strict=True) != directory or not stat.S_ISDIR(directory.lstat().st_mode):
                    raise MaintenanceControlError('state_unavailable')
                info = directory.lstat()
                if info.st_uid != os.geteuid() or info.st_mode & 0o022:
                    raise MaintenanceControlError('state_unavailable')
            except OSError:
                raise MaintenanceControlError('state_unavailable') from None

    @staticmethod
    def _present(path: Path, *, directory: bool = False) -> bool:
        try:
            info = path.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            raise MaintenanceControlError('state_unavailable') from None
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected(info.st_mode):
            raise MaintenanceControlError('state_unavailable')
        return True

    def status(self) -> dict[str, bool]:
        try:
            self._directories()
            enabled = self._present(self.flag)
            pending = self._present(self.pending) or self._present(self.publication_pending)
            recovery = self._present(self.recovery_lock, directory=True)
            return {'enabled': enabled or pending, 'transition_pending': pending,
                    'recovery_held': recovery, 'state_uncertain': False}
        except (OSError, MaintenanceControlError):
            return {'enabled': True, 'transition_pending': True,
                    'recovery_held': True, 'state_uncertain': True}

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        self._directories()
        fd = None
        try:
            fd = os.open(self.lock, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
                raise MaintenanceControlError('exclusion_unavailable')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MaintenanceControlError('operation_busy') from None
            if (info.st_dev, info.st_ino) != (self.lock.lstat().st_dev, self.lock.lstat().st_ino):
                raise MaintenanceControlError('exclusion_unavailable')
            yield
        except OSError:
            raise MaintenanceControlError('exclusion_unavailable') from None
        finally:
            if fd is not None:
                os.close(fd)

    def _sync_directory(self) -> None:
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _create(self, path: Path, raw: bytes, mode: int) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        try:
            os.fchmod(fd, mode)
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        self._sync_directory()

    def _enable(self) -> None:
        if not self._present(self.flag):
            self._create(self.flag, b'', 0o644)

    def _append_audit(self, operation: str, actor: str, source: str, request_id: str, phase: str) -> None:
        item = {'schema_version': 1, 'event': 'security.maintenance.' + phase,
                'operation': operation, 'actor': actor, 'source': source, 'request_id': request_id,
                'observed_at': datetime.now(timezone.utc).isoformat()}
        raw = (json.dumps(item, sort_keys=True) + '\n').encode()
        fd = os.open(self.audit, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600):
                raise MaintenanceControlError('audit_unavailable')
            # One bounded append while the shared operation lock is held.
            if os.write(fd, raw) != len(raw):
                raise MaintenanceControlError('audit_unavailable')
            os.fsync(fd)
        finally:
            os.close(fd)
        self._sync_directory()

    @staticmethod
    def _identity(actor: str, source: str) -> None:
        if (not isinstance(actor, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}', actor) is None
            or source not in ('web', 'cli')):
            raise MaintenanceControlError('invalid_request')

    def change(self, enabled: bool, *, actor: str, source: str) -> dict[str, bool]:
        if type(enabled) is not bool:
            raise MaintenanceControlError('invalid_request')
        self._identity(actor, source)
        operation = 'enable' if enabled else 'disable'
        with self._exclusive():
            current = self.status()
            if current['state_uncertain']:
                raise MaintenanceControlError('state_unavailable')
            if current['transition_pending']:
                raise MaintenanceControlError('transition_requires_host_repair')
            # Any durable lock directory is a hold, including one with no owner file.
            if not enabled and current['recovery_held']:
                raise MaintenanceControlError('recovery_held')
            request_id = uuid.uuid4().hex
            self._create(self.pending, (request_id + '\n').encode(), 0o600)
            self.checkpoint('pending_durable')
            try:
                self._append_audit(operation, actor, source, request_id, 'requested')
                self.checkpoint('intent_durable')
                if enabled:
                    self._enable()
                else:
                    # Recheck under the shared exclusion immediately before opening.
                    if self._present(self.recovery_lock, directory=True):
                        raise MaintenanceControlError('recovery_held')
                    self.flag.unlink(missing_ok=True)
                    self._sync_directory()
                self.checkpoint('flag_durable')
                self._append_audit(operation, actor, source, request_id, 'completed')
                self.checkpoint('completion_durable')
                self.pending.unlink()
                self._sync_directory()
            except BaseException:
                # Preserve the pending marker for host repair. Best effort also
                # preserves compatibility with the older single-flag boundary.
                try:
                    self._enable()
                except Exception:
                    pass
                raise MaintenanceControlError('transition_incomplete') from None
            return self.status()

    def recover_hold(self, *, actor: str) -> dict[str, bool]:
        """Host-only repair forces maintenance on; never reopens or releases recovery."""
        self._identity(actor, 'cli')
        with self._exclusive():
            if self._present(self.pending):
                fd = os.open(self.pending, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
                        raise MaintenanceControlError('state_unavailable')
                    raw = os.read(fd, 65537)
                finally:
                    os.close(fd)
                try:
                    pending = json.loads(raw)
                except (ValueError, UnicodeError):
                    pending = None
                if isinstance(pending, dict) and pending.get('operation') == 'publication-completion':
                    raise MaintenanceControlError('publication_completion_requires_host_handoff')
            self._enable()
            request_id = uuid.uuid4().hex
            self._append_audit('recover_hold', actor, 'cli', request_id, 'completed')
            if self._present(self.pending):
                self.pending.unlink()
                self._sync_directory()
            return self.status()
