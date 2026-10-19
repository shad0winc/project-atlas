"""Actual update shell plus actual maintenance authority; external runtime is stubbed."""
from pathlib import Path
import subprocess

import pytest

from tests.core import test_update_transaction as fixtures

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('point', ('before_publication', 'after_publication', 'after_owner_release',
                                   'publication_refused', 'release_refused', 'success'))
def test_native_update_retains_maintenance_across_completion_boundaries(tmp_path, monkeypatch, point):
    environment = fixtures.prepare_runtime(tmp_path)
    runtime = Path(environment['ATLAS_RUNTIME_CONFIG_DIR'])
    (runtime / 'maintenance').mkdir(mode=0o700)
    environment['ATLAS_REAL_MAINTENANCE_COMMAND'] = str(ROOT / 'scripts/commands/maintenance.sh')
    environment['ATLAS_TEST_COMPLETION_POINT'] = point
    original = subprocess.run
    injected = False

    def invoke(args, *positional, **kwargs):
        nonlocal injected
        if (isinstance(args, list) and args[:2] == ['bash', '-c']
                and 'atlas_command_update "$1" --migration none' in args[2]):
            assert not injected
            injected = True
            args = list(args)
            hook = r'''
# Replace mocked control functions with the real host authority, on fixture state.
source "$ATLAS_REAL_MAINTENANCE_COMMAND"
original_complete="$(declare -f atlas_deployment_complete_update)"
eval "${original_complete/atlas_deployment_complete_update ()/atlas_fixture_complete_update ()}"
atlas_deployment_complete_update() {
  case "$ATLAS_TEST_COMPLETION_POINT" in
    before_publication) kill -KILL "$$" ;;
    publication_refused) return 1 ;;
  esac
  atlas_fixture_complete_update "$@" || return 1
  if [[ "$ATLAS_TEST_COMPLETION_POINT" == after_publication ]]; then kill -KILL "$$"; fi
}
original_release="$(declare -f atlas_deployment_release_lock)"
eval "${original_release/atlas_deployment_release_lock ()/atlas_fixture_release_lock ()}"
atlas_deployment_release_lock() {
  [[ "$ATLAS_TEST_COMPLETION_POINT" != release_refused ]] || return 1
  atlas_fixture_release_lock "$@" || return 1
  if [[ "$ATLAS_TEST_COMPLETION_POINT" == after_owner_release ]]; then kill -KILL "$$"; fi
}
'''
            args[2] = args[2].replace('atlas_command_update "$1" --migration none',
                                    hook + '\natlas_command_update "$1" --migration none')
        return original(args, *positional, **kwargs)

    monkeypatch.setattr(subprocess, 'run', invoke)
    result = fixtures.run_update(environment)
    assert injected
    assert (runtime / 'maintenance/enabled').is_file(), result.stderr
    assert not (runtime / 'maintenance/control-pending').exists(), result.stderr
    assert 'maintenance:disable' not in fixtures.event_lines(environment)
    owner = runtime / 'deployments/update.lock/owner'
    if point in ('before_publication', 'after_publication', 'publication_refused', 'release_refused'):
        assert owner.is_file(), result.stderr
        assert 'deployment_id=update-' in owner.read_text()
    else:
        assert not owner.exists(), result.stderr
    current = (runtime / 'deployments/current').read_text().strip()
    if point in ('before_publication', 'publication_refused'):
        assert current == 'baseline-test'
    else:
        assert current.startswith('update-'), result.stderr
    if point in ('before_publication', 'after_publication', 'after_owner_release'):
        assert result.returncode == -9, result.stderr
    elif point == 'success':
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0


def test_native_transactions_have_no_ordinary_reopen_path():
    for relative in ('scripts/commands/update.sh', 'scripts/commands/deployment.sh'):
        source = (ROOT / relative).read_text()
        assert 'atlas_command_maintenance disable' not in source
        assert 'atlas_maintenance_transaction_hold' in source


@pytest.mark.parametrize('state', ('missing', 'pending'))
def test_held_checkpoint_refuses_missing_or_interrupted_flag(tmp_path, state):
    import fcntl
    from atlas.maintenance_transaction import TransactionMaintenanceAuthority
    from atlas.maintenance_control import MaintenanceControlError

    for name in ('maintenance', 'deployments', 'deployments/update.lock'):
        (tmp_path / name).mkdir(mode=0o700)
    owner = tmp_path / 'deployments/update.lock/owner'
    owner.write_text('deployment_id=update-fixture\n')
    if state == 'pending':
        (tmp_path / 'maintenance/enabled').touch()
        (tmp_path / 'maintenance/control-pending').touch()
    lock = tmp_path / 'deployment-scheduler.lock';lock.touch(mode=0o600)
    with lock.open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        authority = TransactionMaintenanceAuthority(tmp_path, 'update-fixture', stream.fileno())
        with pytest.raises(MaintenanceControlError):authority.verify_hold(actor='fixture')
    assert owner.read_text() == 'deployment_id=update-fixture\n'
    assert not (tmp_path / 'maintenance/control-audit.jsonl').exists()
