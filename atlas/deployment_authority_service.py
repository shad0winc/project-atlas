"""Bounded authority service lifecycle under a held component journal.

Only daemon-reload and start/stop of the exact authority unit are executable.
A pinned native verifier supplies process/Unix-listener provenance checks. This
module does not install code, enable services, touch Docker, or reopen admission.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import shutil
import subprocess
import time

from atlas.deployment_component_rollout import SURFACES, digest, observation, require
from atlas.deployment_publication_journal import read_file
from atlas.deployment_authority_unit import UNIT_NAME
from atlas.maintenance_control import MaintenanceControlError


class AuthoritySocketNotReady(MaintenanceControlError):
    pass


class NativeAuthorityProbe:
    """Read-only adapter around the accepted native process/socket verifier.

The coordinator must supply the checksum-pinned verifier namespace, record reader,
record and extension. No import from an untrusted/writable source is performed here.
"""
    def __init__(self, verifier, reader, record, extension, *, lookup_roots=None):
        self.verifier, self.reader, self.record, self.extension = verifier, reader, Path(record), extension
        self.unit = Path(extension['authority']['unit_path'])
        self.socket = Path(extension['authority']['socket'])
        self.source = Path(extension['caddy']['immutable_source'])
        require(self.unit == Path('/etc/systemd/system') / UNIT_NAME
                and self.socket == Path('/run/atlas-maintenance-control/control.sock')
                and self.source.parent.parent == Path('/mnt/storage/configs/atlas/deployments/repairs')
                and self.source.name == 'source', 'authority_lifecycle_paths_differ')
        self.unit_sha256 = read_file(self.record / 'maintenance-authority.service')
        self.target_fingerprint = digest({'schema_version': 1, 'unit': str(self.unit), 'unit_sha256': self.unit_sha256,
            'source': str(self.source), 'socket': str(self.socket), 'peer_uid': 999, 'socket_gid': 20000})
        self.lookup_roots = tuple(Path(path) for path in (lookup_roots or
            ('/etc/systemd/system', '/run/systemd/system', '/usr/local/lib/systemd/system',
             '/usr/lib/systemd/system', '/lib/systemd/system')))

    def properties(self):return self.verifier['service_properties']()

    def preflight(self, *, require_unit=False):
        require(not any(os.environ.get(key) for key in ('DBUS_SYSTEM_BUS_ADDRESS', 'DBUS_SESSION_BUS_ADDRESS',
                    'SYSTEMD_BUS_ADDRESS', 'SYSTEMD_HOST', 'SYSTEMD_MACHINE', 'SYSTEMD_UNIT_PATH', 'SYSTEMD_OFFLINE')),
                'authority_systemd_environment_overridden')
        executable = shutil.which('systemctl')
        require(executable is not None and Path(executable).resolve(strict=True) == Path('/usr/bin/systemctl').resolve(strict=True),
                'authority_systemctl_query_executable_differs')
        # Include generic and dash-prefix drop-ins even before daemon-reload has
        # made an override visible in the manager's cached DropInPaths property.
        for root in self.lookup_roots:
            candidate = root / UNIT_NAME
            if candidate != self.unit:
                require(not candidate.exists() and not candidate.is_symlink(), 'authority_shadow_unit_present')
            for name in ('service.d', 'atlas-.service.d', 'atlas-maintenance-.service.d', UNIT_NAME + '.d'):
                path = root / name
                require(not path.exists() and not path.is_symlink(), 'authority_dropin_path_present')
        exists = self.unit.exists() or self.unit.is_symlink()
        require(not require_unit or exists, 'authority_unit_not_installed')
        if exists:
            info = self.unit.lstat()
            require(stat.S_ISREG(info.st_mode) and not self.unit.is_symlink() and info.st_nlink == 1
                    and info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o644
                    and read_file(self.unit) == self.unit_sha256, 'authority_installed_unit_differs')
        properties = self.properties()
        require(properties['DropInPaths'] == '' and properties['FragmentPath'] in ('', str(self.unit))
                and properties['LoadState'] in ('loaded', 'not-found'), 'authority_effective_unit_differs')
        raw = self.verifier['query'](['systemctl', 'show', UNIT_NAME, '--property=UnitFileState', '--value'])
        require(raw.decode().strip() in ('', 'disabled', 'static', 'not-found'), 'authority_boot_enablement_not_planned')
        return properties

    def observe(self):
        properties = self.preflight()
        if properties['ActiveState'] == 'inactive':
            require(properties['SubState'] == 'dead' and properties['MainPID'] == '0'
                    and not self.socket.parent.exists() and not self.socket.parent.is_symlink(),
                    'authority_inactive_boundary_unproven')
            require(properties == self.properties(), 'authority_inactive_identity_changed')
            return {'fingerprint': 'absent', 'identity': 'absent'}
        require(properties['ActiveState'] == 'active' and properties['SubState'] == 'running',
                'authority_service_transitional_or_failed')
        require(self.unit.exists() and not self.unit.is_symlink(), 'authority_active_unit_missing')
        try:
            verified = self.verifier['verify_authority'](self.reader, self.record, self.extension)
        except FileNotFoundError:
            # Retry only a not-yet-present listener under unchanged running service
            # properties; unit/process/contract errors otherwise remain failures.
            if (not self.socket.exists() and not self.socket.is_symlink()
                    and properties == self.properties()):
                self.verifier['authority_properties'](properties, str(self.source), self.extension['authority'])
                raise AuthoritySocketNotReady('authority_socket_not_ready') from None
            raise
        require(verified == properties, 'authority_process_changed_during_observation')
        socket = self.socket.lstat()
        require(properties == self.properties(), 'authority_service_changed_during_observation')
        return {'fingerprint': self.target_fingerprint, 'identity': digest({'properties': properties,
            'socket_device': socket.st_dev, 'socket_inode': socket.st_ino, 'socket_ctime_ns': socket.st_ctime_ns})}

    def removed(self):
        state = self.observe()
        properties = self.properties()
        return (state['fingerprint'] == 'absent' and properties['LoadState'] == 'not-found'
                and properties['FragmentPath'] == '' and properties['NeedDaemonReload'] == 'no'
                and not self.unit.exists() and not self.unit.is_symlink())


class AuthorityServiceLifecycle:
    def __init__(self, probe, *, held_guard, execute=None, startup_timeout=15):
        require(callable(held_guard) and all(callable(getattr(probe, name, None)) for name in
                    ('observe', 'preflight', 'removed')), 'authority_lifecycle_probe_incomplete')
        require(isinstance(startup_timeout, (int, float)) and 0 <= startup_timeout <= 30,
                'authority_lifecycle_startup_bound_invalid')
        self.probe, self.held_guard = probe, held_guard
        self.execute = execute or self._execute
        self.startup_timeout = startup_timeout
        self.target_fingerprint = probe.target_fingerprint

    @staticmethod
    def _execute(command):
        # Even direct internal executor calls are restricted to this fixed set.
        prefix = ('/usr/bin/systemctl', '--system', '--no-ask-password', '--no-pager')
        allowed = (prefix + ('daemon-reload',), prefix + ('start', UNIT_NAME), prefix + ('stop', UNIT_NAME))
        require(isinstance(command, (list, tuple)) and tuple(command) in allowed, 'authority_systemd_command_not_allowed')
        # No inherited shell, PATH, PYTHONPATH, pager, remote bus or user-manager setting.
        try:
            result = subprocess.run(command, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C',
                 'SYSTEMD_PAGER': 'cat', 'SYSTEMD_COLORS': '0'}, stdin=subprocess.DEVNULL,
                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise MaintenanceControlError('authority_systemd_command_uncertain') from None
        require(result.returncode == 0, 'authority_systemd_command_failed')
        return True

    def _held(self):require(self.held_guard() is True, 'authority_service_hold_unproven')

    def _command(self, operation, *, expected):
        require(operation in ('daemon-reload', 'start', 'stop'), 'authority_systemd_operation_refused')
        self._held();self.probe.preflight(require_unit=operation == 'start')
        require(self.observe() == expected, 'authority_service_action_identity_changed')
        command = ['/usr/bin/systemctl', '--system', '--no-ask-password', '--no-pager', operation]
        if operation != 'daemon-reload': command.append(UNIT_NAME)
        require(self.execute(command) is True, 'authority_systemd_command_unconfirmed')
        self._held()

    def observe(self):
        self._held();value = observation(self.probe.observe());self._held();return value

    def apply(self):
        state = self.observe()
        if state['fingerprint'] == self.target_fingerprint:return
        require(state['fingerprint'] == 'absent', 'authority_start_precondition_changed')
        self._command('daemon-reload', expected=state);self._command('start', expected=state)
        deadline = time.monotonic() + self.startup_timeout
        while True:
            self._held()
            try:
                state = self.observe()
                require(state['fingerprint'] == self.target_fingerprint, 'authority_started_identity_unproven')
                return
            except AuthoritySocketNotReady:
                # Type=simple can report running just before its socket is bound.
                # Contract failures are not retried or converted into readiness.
                require(time.monotonic() < deadline, 'authority_socket_startup_timeout')
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))

    def rollback(self):
        state = self.observe()
        if state['fingerprint'] == 'absent':return
        require(state['fingerprint'] == self.target_fingerprint, 'authority_stop_precondition_changed')
        self._command('stop', expected=state)
        require(self.observe()['fingerprint'] == 'absent', 'authority_stop_not_proven')

    def confirm(self, mode, expected):
        require(mode in ('apply', 'rollback'), 'authority_service_confirmation_mode_invalid')
        expected = observation(expected)
        require(expected['fingerprint'] == (self.target_fingerprint if mode == 'apply' else 'absent'),
                'authority_service_confirmation_target_differs')
        require(self.observe() == expected, 'authority_service_confirmation_identity_changed')
        again = self.observe()
        require(again == expected, 'authority_service_confirmation_identity_changed')
        return again

    def unit_retained(self):
        state = self.observe()
        require(state['fingerprint'] == 'absent', 'authority_unit_removal_service_active')
        self._command('daemon-reload', expected=state)
        require(self.probe.removed() is True, 'authority_unit_manager_removal_not_proven')
        self._held();return True

    def verify(self, mode):
        require(mode in ('apply', 'rollback'), 'authority_service_verification_mode_invalid')
        state = self.observe()
        require(state['fingerprint'] == (self.target_fingerprint if mode == 'apply' else 'absent'),
                'authority_service_final_state_differs')
        if mode == 'rollback': require(self.probe.removed() is True, 'authority_service_manager_not_restored')
        self._held();return True


class AuthorityServiceRolloutAdapter:
    def __init__(self, lifecycle, components, *, held_guard):
        self.lifecycle, self.components, self.held_guard = lifecycle, components, held_guard
        require(all(callable(getattr(components, name, None)) for name in
                    ('observe', 'apply', 'rollback', 'confirm', 'verify', 'source_inactive')),
                'authority_service_component_adapter_incomplete')

    def _held(self):require(self.held_guard() is True, 'authority_service_adapter_hold_unproven')
    def _name(self, name):require(name in SURFACES[2:], 'authority_service_adapter_unknown_surface')
    def observe(self, name):
        self._name(name);self._held()
        result = self.lifecycle.observe() if name == 'authority-service' else observation(self.components.observe(name))
        self._held();return result
    def apply(self, name):
        self._name(name);self._held()
        if name == 'authority-service':self.lifecycle.apply()
        else:self.components.apply(name)
        self._held()
    def rollback(self, name):
        self._name(name);self._held()
        if name == 'authority-service':self.lifecycle.rollback()
        else:self.components.rollback(name)
        self._held()
    def confirm(self, name, mode, expected):
        self._name(name);self._held()
        result = self.lifecycle.confirm(mode, expected) if name == 'authority-service' else self.components.confirm(name, mode, expected)
        require(observation(result) == observation(expected), 'authority_service_adapter_confirmation_changed')
        self._held();return result
    def verify(self, mode):
        self._held();require(self.lifecycle.verify(mode) is True and self.components.verify(mode) is True,
                             'authority_service_adapter_final_verification_failed')
        self._held();return True
    def authority_inactive(self):return self.lifecycle.observe()['fingerprint'] == 'absent'
    def source_inactive(self):
        self._held();result = self.authority_inactive() and self.components.source_inactive() is True
        self._held();return result
    def unit_retained(self):return self.lifecycle.unit_retained()
