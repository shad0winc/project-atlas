"""Writer shutdown proof and held-failure behavior using isolated Docker stubs."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/core'))
import test_restore_live_orchestration as orchestration
import test_restore_live_transaction as transaction


class RestoreQuiescenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def docker(self, state='false|exited|0|false', *, stop_failure='', inspect_failure=False):
        executable = self.root / 'docker'
        executable.write_text('''#!/usr/bin/env bash
set -euo pipefail
echo "$1 ${@: -1}" >> "$EVENTS"
if [[ "$1" == inspect ]]; then
  [[ "$INSPECT_FAILURE" == false ]] || exit 1
  printf '%s\\n' "$STOP_STATE"
elif [[ "$1" == stop && "${@: -1}" == "$STOP_FAILURE" ]]; then
  exit 1
fi
''')
        executable.chmod(0o755)
        return {'PATH': str(self.root) + ':' + os.environ['PATH'],
                'EVENTS': str(self.root / 'events'), 'STOP_STATE': state,
                'STOP_FAILURE': stop_failure, 'INSPECT_FAILURE': str(inspect_failure).lower()}

    def test_only_clean_or_sigterm_stopped_states_are_accepted(self):
        for state in ('false|exited|0|false', 'false|exited|143|false'):
            result = orchestration._bash('source "$RESTORE_COMMAND"; atlas_restore_require_writers_quiesced', self.docker(state))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_running_restarting_oom_kill_force_kill_and_worker_failure_are_rejected(self):
        for state in ('true|running|0|false', 'false|restarting|0|false',
                      'false|exited|137|false', 'false|exited|0|true',
                      'false|exited|1|false', 'unparseable-private-state'):
            with self.subTest(state=state):
                result = orchestration._bash('source "$RESTORE_COMMAND"; atlas_restore_require_writers_quiesced', self.docker(state))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('did not stop cleanly', result.stderr)
                self.assertNotIn(state, result.stderr)

    def test_inspect_failure_cannot_be_treated_as_stopped(self):
        result = orchestration._bash('source "$RESTORE_COMMAND"; atlas_restore_require_writers_quiesced', self.docker(inspect_failure=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unable to verify', result.stderr)

    def test_stop_failure_short_circuits_before_later_writers(self):
        env = self.docker(stop_failure='atlas-sports-controller')
        result = orchestration._bash('source "$RESTORE_COMMAND"; atlas_restore_stop_writers', env)
        self.assertNotEqual(result.returncode, 0)
        events = (self.root / 'events').read_text().splitlines()
        self.assertIn('stop atlas-api', events)
        self.assertIn('stop atlas-sports-controller', events)
        self.assertNotIn('stop atlas-sports-writer', events)
        self.assertFalse(any(line.startswith('start ') for line in events))

    def test_completed_stop_rechecks_all_four_writers(self):
        result = orchestration._bash('source "$RESTORE_COMMAND"; atlas_restore_stop_writers', self.docker())
        self.assertEqual(result.returncode, 0, result.stderr)
        events = (self.root / 'events').read_text().splitlines()
        self.assertEqual(events[-4:], ['inspect atlas-api', 'inspect atlas-sports-controller',
                         'inspect atlas-notifications-worker', 'inspect atlas-sports-writer'])

    def apply_failure(self, override):
        script, env = transaction._base(self.root, override)
        try:
            result = transaction._run(script + '\natlas_restore_apply_live "$STAGE"\n', env)
        finally:
            transaction._cleanup_stage(env)
        self.assertNotEqual(result.returncode, 0)
        return result, Path(env['EVENTS']).read_text().splitlines()

    def test_post_backup_writer_restart_prevents_state_application(self):
        result, events = self.apply_failure('''
atlas_restore_require_writers_quiesced() { echo writers:changed >> "$EVENTS"; return 1; }
''')
        self.assertIn('backup:create', events)
        self.assertIn('writers:changed', events)
        self.assertNotIn('state:apply', events)
        self.assertEqual(events[-4:], ['writers:start', 'writers:ready', 'maintenance:retain', 'lock:release'])

    def test_incomplete_application_revert_does_not_restart_consumers(self):
        result, events = self.apply_failure('''
atlas_backup_recovery_apply_staged_state() {
  echo state:partial >> "$EVENTS"
  mkdir -p "$2"
  echo applying > "$2/status"
  return 1
}
''')
        self.assertIn('state:partial', events)
        self.assertNotIn('writers:start', events)
        self.assertNotIn('maintenance:retain', events)
        self.assertNotIn('lock:release', events)
        self.assertIn('Maintenance: retained', result.stderr)

    def test_reverted_but_invalid_state_does_not_restart_consumers(self):
        _, events = self.apply_failure('''
atlas_backup_recovery_apply_staged_state() {
  mkdir -p "$2"; echo reverted > "$2/status"; return 1
}
atlas_restore_validate_live_consumers() { echo consumers:invalid >> "$EVENTS"; return 1; }
''')
        self.assertIn('consumers:invalid', events)
        self.assertNotIn('writers:start', events)
        self.assertNotIn('lock:release', events)

    def test_validated_reverted_state_can_restart_under_held_maintenance(self):
        _, events = self.apply_failure('''
atlas_backup_recovery_apply_staged_state() {
  mkdir -p "$2"; echo reverted > "$2/status"; return 1
}
''')
        self.assertLess(events.index('consumers:live'), events.index('writers:start'))
        self.assertNotIn('maintenance:retain', events)
        self.assertNotIn('lock:release', events)

    def test_failed_revert_keeps_writers_stopped(self):
        _, events = self.apply_failure('''
atlas_restore_validate_live_consumers() { return 1; }
atlas_backup_recovery_revert_applied_state() { echo revert:failed >> "$EVENTS"; return 1; }
''')
        self.assertIn('revert:failed', events)
        self.assertNotIn('writers:start', events)
        self.assertNotIn('lock:release', events)

    def test_resume_invalid_state_keeps_writers_stopped(self):
        script, env, _ = transaction._held_environment(self.root, 'applied-awaiting-verification')
        script += '\natlas_restore_validate_live_consumers() { return 1; }\natlas_restore_resume_live restore-held\n'
        result = transaction._run(script, env)
        self.assertNotEqual(result.returncode, 0)
        events = Path(env['EVENTS']).read_text().splitlines()
        self.assertIn('writers:stop', events)
        self.assertNotIn('writers:start', events)
        self.assertNotIn('lock:release', events)

    def test_abort_invalid_reverted_state_keeps_writers_stopped(self):
        script, env, _ = transaction._held_environment(self.root, 'applied-awaiting-verification')
        script += '\natlas_restore_validate_live_consumers() { return 1; }\natlas_restore_abort_live restore-held\n'
        result = transaction._run(script, env)
        self.assertNotEqual(result.returncode, 0)
        events = Path(env['EVENTS']).read_text().splitlines()
        self.assertIn('state:revert', events)
        self.assertNotIn('writers:start', events)
        self.assertNotIn('lock:release', events)


if __name__ == '__main__': unittest.main()
