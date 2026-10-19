from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMMAND = ROOT / 'scripts/commands/maintenance.sh'


@pytest.fixture
def runtime(tmp_path):
    for name in ('maintenance', 'deployments'):
        (tmp_path / name).mkdir(mode=0o700)
    (tmp_path / 'deployment-scheduler.lock').touch(mode=0o600)
    return tmp_path


def command(runtime, action, **extra):
    env = {**os.environ, 'ATLAS_RUNTIME_CONFIG_DIR': str(runtime), **extra}
    env.pop('ATLAS_MAINTENANCE_DIR', None)
    if 'ATLAS_MAINTENANCE_DIR' in extra:
        env['ATLAS_MAINTENANCE_DIR'] = extra['ATLAS_MAINTENANCE_DIR']
    return subprocess.run(['bash', '-c', 'set -euo pipefail; source "$1"; atlas_command_maintenance "$2"',
                           'maintenance-test', str(COMMAND), action], env=env, capture_output=True, text=True)


def test_cli_fallback_transitions_are_audited_without_api_or_socket(runtime):
    assert command(runtime, 'status').stdout.strip() == 'Atlas maintenance mode: disabled'
    assert command(runtime, 'enable').returncode == 0
    assert (runtime / 'maintenance/enabled').is_file()
    assert command(runtime, 'disable').returncode == 0
    assert not (runtime / 'maintenance/enabled').exists()
    entries = [json.loads(line) for line in (runtime / 'maintenance/control-audit.jsonl').read_text().splitlines()]
    assert [(row['operation'], row['event']) for row in entries] == [
        ('enable', 'security.maintenance.requested'), ('enable', 'security.maintenance.completed'),
        ('disable', 'security.maintenance.requested'), ('disable', 'security.maintenance.completed')]
    assert all(row['source'] == 'cli' and row['actor'] == f'uid:{os.geteuid()}' for row in entries)


def test_cli_cannot_disable_original_recovery_hold(runtime):
    assert command(runtime, 'enable').returncode == 0
    lock = runtime / 'deployments/update.lock';lock.mkdir()
    owner = lock / 'deployment';owner.write_bytes(b'original-failed-transaction\n')
    before = owner.read_bytes()
    assert command(runtime, 'disable').returncode == 1
    assert (runtime / 'maintenance/enabled').is_file()
    assert owner.read_bytes() == before
    assert command(runtime, 'status').stdout.strip() == 'Atlas maintenance mode: enabled'


@pytest.mark.parametrize('operation', ('enable', 'disable', 'repair-hold'))
def test_cli_does_not_reenter_or_bypass_transaction_flock(runtime, operation):
    flag = runtime / 'maintenance/enabled';flag.touch()
    with (runtime / 'deployment-scheduler.lock').open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert command(runtime, operation).returncode == 1
    assert flag.is_file()
    assert not (runtime / 'maintenance/control-audit.jsonl').exists()


def test_pending_requires_explicit_host_repair_and_preserves_recovery(runtime):
    pending = runtime / 'maintenance/control-pending';pending.write_text('interrupted\n')
    recovery = runtime / 'deployments/update.lock';recovery.mkdir()
    assert command(runtime, 'disable').returncode == 1
    assert command(runtime, 'repair-hold').returncode == 0
    assert not pending.exists()
    assert (runtime / 'maintenance/enabled').is_file() and recovery.is_dir()
    assert command(runtime, 'disable').returncode == 1


@pytest.mark.parametrize('kind', ('symlink', 'ordinary-file'))
def test_uncertain_recovery_ownership_refuses_open(runtime, kind):
    flag = runtime / 'maintenance/enabled';flag.touch()
    lock = runtime / 'deployments/update.lock'
    if kind == 'symlink':lock.symlink_to(runtime / 'absent')
    else:lock.touch()
    assert command(runtime, 'status').returncode == 1
    assert command(runtime, 'disable').returncode == 1
    assert flag.is_file()


def test_missing_flock_is_not_silently_created(runtime):
    (runtime / 'deployment-scheduler.lock').unlink()
    assert command(runtime, 'enable').returncode == 1
    assert not (runtime / 'deployment-scheduler.lock').exists()


def test_audit_failure_keeps_durable_pending_hold(runtime):
    (runtime / 'maintenance/enabled').touch()
    outside = runtime / 'outside';outside.write_bytes(b'unchanged')
    (runtime / 'maintenance/control-audit.jsonl').symlink_to(outside)
    assert command(runtime, 'disable').returncode == 1
    assert (runtime / 'maintenance/enabled').is_file()
    assert (runtime / 'maintenance/control-pending').is_file()
    assert outside.read_bytes() == b'unchanged'


def test_legacy_directory_override_cannot_bypass_authority(runtime):
    override = runtime / 'other'
    assert command(runtime, 'enable', ATLAS_MAINTENANCE_DIR=str(override)).returncode == 1
    assert not override.exists()
