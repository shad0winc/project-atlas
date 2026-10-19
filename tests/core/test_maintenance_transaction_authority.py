from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from atlas.maintenance_transaction import TransactionMaintenanceAuthority
from atlas.maintenance_control import MaintenanceControlError

ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = 'update-private-fixture'


@pytest.fixture
def runtime(tmp_path):
    for name in ('maintenance', 'deployments', 'deployments/update.lock'):
        (tmp_path / name).mkdir(mode=0o700)
    (tmp_path / 'deployments/update.lock/owner').write_text('deployment_id=' + IDENTIFIER + '\npid=123\n')
    (tmp_path / 'deployment-scheduler.lock').touch(mode=0o600)
    return tmp_path


def shell_enable(runtime, fd, identifier=IDENTIFIER):
    env = {**os.environ, 'ATLAS_RUNTIME_CONFIG_DIR': str(runtime)}
    env.pop('ATLAS_MAINTENANCE_DIR', None)
    return subprocess.run(['bash', '-c',
        'set -euo pipefail; source "$1"; atlas_maintenance_transaction_enable "$2" "$3"',
        'transaction-test', str(ROOT / 'scripts/commands/maintenance.sh'), identifier, str(fd)],
        pass_fds=(fd,), env=env, capture_output=True, text=True)


def assert_parent_still_exclusive(runtime):
    with (runtime / 'deployment-scheduler.lock').open('r') as probe:
        with pytest.raises(BlockingIOError):
            fcntl.flock(probe.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)


def test_real_shell_child_enables_without_unlocking_parent_or_recovery(runtime):
    owner = runtime / 'deployments/update.lock/owner';before = owner.read_bytes()
    with (runtime / 'deployment-scheduler.lock').open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = shell_enable(runtime, stream.fileno())
        assert result.returncode == 0, result.stderr
        assert_parent_still_exclusive(runtime)
    assert (runtime / 'maintenance/enabled').is_file()
    assert owner.read_bytes() == before
    audit = [json.loads(line) for line in (runtime / 'maintenance/control-audit.jsonl').read_text().splitlines()]
    assert [item['event'] for item in audit] == ['security.maintenance.requested', 'security.maintenance.completed']


@pytest.mark.parametrize('lock_mode', (None, fcntl.LOCK_SH))
def test_unlocked_or_shared_descriptor_cannot_claim_exclusive_parent(runtime, lock_mode):
    with (runtime / 'deployment-scheduler.lock').open('r+') as stream:
        if lock_mode is not None:fcntl.flock(stream.fileno(), lock_mode | fcntl.LOCK_NB)
        assert shell_enable(runtime, stream.fileno()).returncode == 1
    assert not (runtime / 'maintenance/enabled').exists()
    assert not (runtime / 'maintenance/control-pending').exists()


def test_wrong_transaction_identity_preserves_owner_and_parent_exclusion(runtime):
    owner = runtime / 'deployments/update.lock/owner';before = owner.read_bytes()
    with (runtime / 'deployment-scheduler.lock').open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert shell_enable(runtime, stream.fileno(), 'update-someone-else').returncode == 1
        assert_parent_still_exclusive(runtime)
    assert owner.read_bytes() == before and not (runtime / 'maintenance/enabled').exists()


def test_unrelated_open_description_cannot_borrow_another_owner_lock(runtime):
    with (runtime / 'deployment-scheduler.lock').open('r+') as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (runtime / 'deployment-scheduler.lock').open('r+') as unrelated:
            assert shell_enable(runtime, unrelated.fileno()).returncode == 1
        assert_parent_still_exclusive(runtime)
    assert not (runtime / 'maintenance/control-pending').exists()


def test_other_inode_descriptor_is_refused(runtime):
    other = runtime / 'other';other.touch()
    with other.open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert shell_enable(runtime, stream.fileno()).returncode == 1
    assert not (runtime / 'maintenance/enabled').exists()


def test_owner_symlink_is_refused_without_following(runtime):
    owner = runtime / 'deployments/update.lock/owner';raw = owner.read_bytes();owner.unlink()
    external = runtime / 'external-owner';external.write_bytes(raw);owner.symlink_to(external)
    with (runtime / 'deployment-scheduler.lock').open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert shell_enable(runtime, stream.fileno()).returncode == 1
    assert external.read_bytes() == raw and not (runtime / 'maintenance/enabled').exists()


def test_borrowed_authority_cannot_disable_or_repair(runtime):
    with (runtime / 'deployment-scheduler.lock').open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        authority = TransactionMaintenanceAuthority(runtime, IDENTIFIER, stream.fileno())
        with pytest.raises(MaintenanceControlError):authority.change(False, actor='uid:0', source='cli')
        with pytest.raises(MaintenanceControlError):authority.change(True, actor='admin', source='web')
        with pytest.raises(MaintenanceControlError):authority.recover_hold(actor='uid:0')
        assert_parent_still_exclusive(runtime)


@pytest.mark.parametrize('phase', ('pending_durable', 'intent_durable', 'flag_durable', 'completion_durable'))
def test_abrupt_enable_exit_preserves_hold_owner_and_parent_lock(runtime, phase):
    owner = runtime / 'deployments/update.lock/owner';before = owner.read_bytes()
    script = '''
import os,sys
from pathlib import Path
from atlas.maintenance_transaction import TransactionMaintenanceAuthority
def stop(phase):
    if phase == sys.argv[4]:os._exit(73)
a = TransactionMaintenanceAuthority(Path(sys.argv[1]),sys.argv[2],int(sys.argv[3]),checkpoint=stop)
a.change(True,actor='fixture',source='cli')
'''
    with (runtime / 'deployment-scheduler.lock').open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run([sys.executable, '-B', '-c', script, str(runtime), IDENTIFIER,
            str(stream.fileno()), phase], pass_fds=(stream.fileno(),), capture_output=True)
        assert result.returncode == 73
        assert_parent_still_exclusive(runtime)
    assert owner.read_bytes() == before
    assert (runtime / 'maintenance/control-pending').is_file()
    assert TransactionMaintenanceAuthority(runtime, IDENTIFIER, 3).status()['enabled'] is True
