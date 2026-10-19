"""Real restore control/locks on disposable state; consumers and backups are stubs."""
from pathlib import Path

import pytest

from tests.core import test_restore_live_transaction as fixtures

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('point', ('before_finalize', 'after_finalize', 'after_owner_release',
                                   'finalize_refused', 'release_refused', 'isolation_refused', 'success'))
def test_restore_keeps_maintenance_at_completion_boundaries(tmp_path, point):
    script, env = fixtures._base(tmp_path)
    runtime = Path(env['ATLAS_RUNTIME_CONFIG_DIR'])
    (runtime / 'maintenance').mkdir(mode=0o700)
    (runtime / 'deployments').mkdir(mode=0o700)
    env['REAL_DEPLOYMENT_COMMAND'] = str(ROOT / 'scripts/commands/deployment.sh')
    env['REAL_MAINTENANCE_COMMAND'] = str(ROOT / 'scripts/commands/maintenance.sh')
    env['COMPLETION_POINT'] = point
    script += r'''
source "$REAL_DEPLOYMENT_COMMAND"
source "$REAL_MAINTENANCE_COMMAND"
atlas_deployment_new_id() { echo restore-test; }
original_finalize="$(declare -f atlas_backup_recovery_finalize_applied_state)"
eval "${original_finalize/atlas_backup_recovery_finalize_applied_state ()/atlas_fixture_finalize ()}"
atlas_backup_recovery_finalize_applied_state() {
  case "$COMPLETION_POINT" in
    before_finalize) kill -KILL "$$" ;;
    finalize_refused) return 1 ;;
  esac
  atlas_fixture_finalize "$@" || return 1
  if [[ "$COMPLETION_POINT" == after_finalize ]]; then kill -KILL "$$"; fi
}
original_release="$(declare -f atlas_deployment_release_lock)"
eval "${original_release/atlas_deployment_release_lock ()/atlas_fixture_release ()}"
atlas_deployment_release_lock() {
  [[ "$COMPLETION_POINT" != release_refused ]] || return 1
  atlas_fixture_release "$@" || return 1
  if [[ "$COMPLETION_POINT" == after_owner_release ]]; then kill -KILL "$$"; fi
}
if [[ "$COMPLETION_POINT" == isolation_refused ]]; then
  atlas_restore_verify_maintenance_isolation() { return 1; }
fi
atlas_restore_apply_live "$STAGE"
'''
    try:
        result = fixtures._run(script, env)
    finally:
        fixtures._cleanup_stage(env)
    assert (runtime / 'maintenance/enabled').is_file(), result.stderr
    assert not (runtime / 'maintenance/control-pending').exists()
    owner = runtime / 'deployments/update.lock/owner'
    if point in ('after_owner_release', 'success'):
        assert not owner.exists(), result.stderr
    else:
        assert owner.read_text().splitlines()[0] == 'deployment_id=restore-test'
    transaction = runtime / 'restores/restore-test'
    if point == 'isolation_refused':
        assert not transaction.exists()
        events = Path(env['EVENTS'])
        assert not events.exists() or 'state:apply' not in events.read_text()
    else:
        status = (transaction / 'status').read_text().strip()
        assert status == ('applied-awaiting-verification' if point in ('before_finalize', 'finalize_refused') else 'verified')
    if point in ('before_finalize', 'after_finalize', 'after_owner_release'):
        assert result.returncode == -9, result.stderr
    elif point == 'success':
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0


@pytest.mark.parametrize('operation', ('resume', 'abort'))
def test_held_restore_refuses_when_shared_exclusion_is_owned(tmp_path, operation):
    import fcntl
    script, env, _ = fixtures._held_environment(tmp_path, 'applied-awaiting-verification')
    runtime = Path(env['ATLAS_RUNTIME_CONFIG_DIR'])
    lock = runtime / 'deployment-scheduler.lock';lock.touch()
    with lock.open('r+') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = fixtures._run(script + '\natlas_restore_' + operation + '_live restore-held\n', env)
    assert result.returncode != 0
    assert not Path(env['EVENTS']).exists()
    assert Path(env['MAINTENANCE_FLAG']).is_file()


def test_restore_has_no_automatic_ordinary_reopen_path():
    source = (ROOT / 'scripts/commands/restore.sh').read_text()
    assert 'atlas_maintenance_disable' not in source
    assert 'atlas_maintenance_transaction_hold' in source
    assert 'maintenance mode to be disabled at preflight' not in source
    assert 'recovery format 2 contains native Sports backend state; live restore is not implemented.' in source
    assert 'recovery format 3 requires native Sports and metadata recovery; live restore is not implemented.' in source
