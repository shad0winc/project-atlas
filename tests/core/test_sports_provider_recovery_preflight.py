from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'scripts/lib/sports-provider-recovery-preflight.py'
UPDATE = ROOT / 'scripts/commands/update.sh'
spec = importlib.util.spec_from_file_location('provider_recovery_preflight', HELPER)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProviderRecoveryPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.now = datetime.now(timezone.utc)
        self.path = self.folder / 'providers.json'
        self.provider = {'thesportsdb': {
            'status': 'degraded',
            'last_error': 'Sports provider is temporarily rate limited.',
            'last_failure_at': self.now.isoformat(),
        }}
        self.path.write_text(json.dumps(self.provider))
        self.report = {
            'schema_version': 1, 'status': 'critical',
            'generated_at': self.now.isoformat(),
            'checks': [
                {'category': category, 'name': name, 'status': 'healthy',
                 'message': 'healthy', 'details': {}}
                for category, name in sorted(module.REQUIRED)
            ],
        }
        self.check = next(c for c in self.report['checks']
                          if (c['category'], c['name']) == module.PROVIDER_ID)
        self.check.update(status='critical',
                          message='Sports provider health is unavailable or degraded',
                          details={'module': 'sports', 'provider_count': 1,
                                   'path': str(module.PROVIDER_FILE)})

    def validate(self, report=None, code=1):
        return module.validate(json.dumps(report or self.report).encode(), code,
                               now=self.now, provider_path=self.path)

    def shell(self, script, *args):
        env = dict(os.environ, ATLAS_PROJECT_DIR=str(ROOT),
                   TEST_UPDATE=str(UPDATE), TEST_FOLDER=str(self.folder))
        return subprocess.run(['bash', '-c', 'source "$TEST_UPDATE"\n' + script,
                               'test', *args], env=env, capture_output=True,
                              text=True, timeout=15)

    def test_exact_rate_limit_produces_sanitized_receipt(self):
        receipt = self.validate()
        self.assertEqual(receipt['admission'], 'thesportsdb-rate-limit-only')
        self.assertEqual(receipt['exception_count'], 1)
        self.assertEqual(receipt['check_count'], 37)
        self.assertNotIn('last_error', json.dumps(receipt))
        self.assertTrue(receipt['post_update_health_required'])

    def test_healthy_race_requires_no_exception_or_provider_file(self):
        self.check['status'] = 'healthy'
        self.report['status'] = 'healthy'
        self.path.unlink()
        self.assertEqual(self.validate(code=0)['exception_count'], 0)

    def test_every_other_required_check_fails_closed_for_all_nonhealthy_statuses(self):
        for check in self.report['checks']:
            if check is self.check:
                continue
            for status in ('critical', 'warning', 'unknown'):
                with self.subTest(name=check['name'], status=status):
                    report = copy.deepcopy(self.report)
                    target = next(c for c in report['checks'] if c['name'] == check['name'])
                    target['status'] = status
                    with self.assertRaises(ValueError):
                        self.validate(report)

    def test_every_missing_required_check_is_refused(self):
        for index in range(len(self.report['checks'])):
            with self.subTest(index=index):
                report = copy.deepcopy(self.report)
                del report['checks'][index]
                with self.assertRaises(ValueError):
                    self.validate(report)

    def test_malformed_duplicate_and_additional_faults_are_refused(self):
        additions = [None, {}, copy.deepcopy(self.check),
                     {'category': 'module:other', 'name': 'Other',
                      'status': 'critical', 'message': 'failure', 'details': {}}]
        for extra in additions:
            with self.subTest(extra=extra):
                report = copy.deepcopy(self.report)
                report['checks'].append(extra)
                with self.assertRaises(ValueError):
                    self.validate(report)

    def test_new_healthy_module_is_allowed(self):
        self.report['checks'].append({'category': 'module:extra', 'name': 'Extra',
                                     'status': 'healthy', 'message': 'ok', 'details': {}})
        self.assertEqual(self.validate()['check_count'], 38)

    def test_report_status_exit_code_and_timestamp_must_agree(self):
        for field, value in [('status', 'healthy'), ('schema_version', 2),
                             ('generated_at', 'invalid'),
                             ('generated_at', (self.now - timedelta(seconds=31)).isoformat()),
                             ('generated_at', (self.now + timedelta(seconds=1)).isoformat()),
                             ('generated_at', self.now.replace(tzinfo=None).isoformat())]:
            with self.subTest(field=field, value=value):
                report = copy.deepcopy(self.report)
                report[field] = value
                with self.assertRaises(ValueError):
                    self.validate(report)
        with self.assertRaises(ValueError):
            self.validate(code=0)

    def test_unavailable_wrong_identity_and_unknown_errors_are_refused(self):
        candidates = [{}, {'other': self.provider['thesportsdb']},
                      {**self.provider, 'espn': {'status': 'healthy'}}]
        for key, value in [('status', 'healthy'), ('last_error', 'secret-url-or-token'),
                           ('last_error', 'TheSportsDB request failed: HTTP 401'),
                           ('last_failure_at', 'invalid'),
                           ('last_failure_at', (self.now - timedelta(seconds=91)).isoformat())]:
            provider = copy.deepcopy(self.provider)
            provider['thesportsdb'][key] = value
            candidates.append(provider)
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.path.write_text(json.dumps(candidate))
                with self.assertRaises(ValueError):
                    self.validate()

    def test_provider_check_details_must_match(self):
        for key, value in [('provider_count', 0), ('provider_count', True),
                           ('provider_count', 2), ('path', '/other'), ('module', 'other')]:
            with self.subTest(key=key, value=value):
                report = copy.deepcopy(self.report)
                check = next(c for c in report['checks'] if c['name'] == 'Provider Health')
                check['details'][key] = value
                with self.assertRaises(ValueError):
                    self.validate(report)

    def test_provider_file_missing_symlink_hardlink_and_oversized_refused(self):
        self.path.unlink()
        with self.assertRaises(OSError):
            self.validate()
        target = self.folder / 'target'
        target.write_text(json.dumps(self.provider))
        self.path.symlink_to(target)
        with self.assertRaises(OSError):
            self.validate()
        self.path.unlink()
        os.link(target, self.path)
        with self.assertRaises(ValueError):
            self.validate()
        self.path.unlink()
        self.path.write_bytes(b' ' * 262145)
        with self.assertRaises(ValueError):
            self.validate()

    def test_duplicate_json_keys_refused(self):
        self.path.write_bytes(b'{"thesportsdb":{},"thesportsdb":{}}')
        with self.assertRaises(ValueError):
            self.validate()
        with self.assertRaises(ValueError):
            module.decode(b'{"checks":[],"checks":[]}', 1024)

    def test_argument_matrix_restricts_recovery_to_all(self):
        cases = [(('all', '--migration', 'none', '--recover-sports-provider'), True),
                 (('all', '--migration', 'none'), True),
                 (('ingress', '--migration', 'none'), True),
                 (('core', '--migration', 'none'), True),
                 (('ingress', '--migration', 'none', '--recover-sports-provider'), False),
                 (('core', '--migration', 'none', '--recover-sports-provider'), False),
                 (('all', '--migration', 'yes', '--recover-sports-provider'), False),
                 (('all', '--migration', 'none', '--unknown'), False),
                 (('all', '--migration', 'none', '--recover-sports-provider', 'extra'), False),
                 (('all',), False)]
        for args, accepted in cases:
            with self.subTest(args=args):
                self.assertEqual(self.shell('atlas_update_validate_arguments "$@"', *args).returncode == 0,
                                 accepted)

    def test_normal_preflight_uses_doctor_and_never_exception(self):
        result = self.shell('''
        atlas_command_doctor() { echo doctor; return 1; }
        atlas_health_python() { echo should-not-run; return 0; }
        atlas_update_preflight '' "$TEST_FOLDER"
        ''')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'doctor')
        self.assertFalse((self.folder / 'provider-recovery-preflight.json').exists())

    def test_unmanaged_sports_refused_before_health_collection(self):
        result = self.shell('''
        atlas_update_sports_managed() { return 1; }
        atlas_health_python() { echo should-not-run; return 0; }
        atlas_update_preflight --recover-sports-provider "$TEST_FOLDER"
        ''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('should-not-run', result.stdout)

    def test_shell_gate_healthy_certificate_exclusive_and_collection_failure(self):
        self.check['status'] = 'healthy'
        self.report['status'] = 'healthy'
        (self.folder / 'report.json').write_text(json.dumps(self.report))
        script = '''
        atlas_update_sports_managed() { return 0; }
        atlas_health_python() { cat "$TEST_FOLDER/report.json"; return "${1:+0}"; }
        atlas_update_preflight --recover-sports-provider "$TEST_FOLDER"
        '''
        result = self.shell(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = self.folder / 'provider-recovery-preflight.json'
        raw = receipt.read_bytes()
        self.assertEqual(json.loads(raw)['admission'], 'fully-healthy')
        self.assertNotEqual(self.shell(script).returncode, 0)
        self.assertEqual(receipt.read_bytes(), raw)
        receipt.unlink()
        result = self.shell('''
        atlas_update_sports_managed() { return 0; }
        atlas_health_python() { echo '{}'; return 2; }
        atlas_update_preflight --recover-sports-provider "$TEST_FOLDER"
        ''')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(receipt.exists())

    def test_post_apply_never_accepts_persistent_degradation(self):
        result = self.shell('''
        atlas_command_doctor() { return 1; }
        atlas_update_transient_sports_provider_health_only() { return 0; }
        atlas_update_readiness_sleep() { echo retry; }
        atlas_update_wait_for_post_apply_health
        ''')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines().count('retry'), 5)
        self.assertIn('grace exhausted', result.stderr)

    def execute_until_acquisition(self, *, recovery=True):
        (self.folder / 'report.json').write_text(json.dumps(self.report))
        script = r'''
        atlas_print_header() { :; }
        atlas_deployment_validate_source() { :; }
        atlas_deployment_require_current_record() { echo previous; }
        atlas_deployment_verify_runtime() { :; }
        atlas_deployment_new_id() { echo update-test; }
        atlas_deployment_acquire_lock() { echo lock; }
        atlas_deployment_prepare_update() { echo capture-rollback; }
        atlas_deployment_record_dir() { echo "$TEST_FOLDER"; }
        atlas_deployment_set_status() { echo "status:$2"; }
        atlas_deployment_release_lock() { echo release; }
        atlas_update_sports_managed() { return 0; }
        atlas_command_doctor() { echo doctor-refused; return 1; }
        atlas_health_python() {
          cat "$TEST_FOLDER/report.json"
          return "$HEALTH_STATUS"
        }
        atlas_update_prepare_scope() { echo artifact-acquisition; return 1; }
        atlas_update_execute_locked "$@"
        '''
        # Pick the health subprocess status consistent with this fixture report.
        status = 0 if self.report['status'] == 'healthy' else 1
        script = f'HEALTH_STATUS={status}\n' + script
        args = ['all', '--migration', 'none']
        if recovery:
            args.append('--recover-sports-provider')
        return self.shell(script, *args)

    def test_transaction_normal_failure_aborts_before_acquisition(self):
        result = self.execute_until_acquisition(recovery=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('status:aborted', result.stdout)
        self.assertIn('release', result.stdout)
        self.assertNotIn('artifact-acquisition', result.stdout)

    def test_transaction_recovery_refusal_aborts_before_acquisition(self):
        self.report['checks'][0]['status'] = 'critical'
        result = self.execute_until_acquisition()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('status:aborted', result.stdout)
        self.assertIn('release', result.stdout)
        self.assertNotIn('artifact-acquisition', result.stdout)

    def test_transaction_admission_retains_acquisition_failure_boundary(self):
        self.check['status'] = 'healthy'
        self.report['status'] = 'healthy'
        result = self.execute_until_acquisition()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('artifact-acquisition', result.stdout)
        self.assertIn('status:aborted', result.stdout)
        self.assertIn('release', result.stdout)
        self.assertTrue((self.folder / 'provider-recovery-preflight.json').is_file())

    def test_all_scope_prepares_and_applies_both_caller_surfaces(self):
        result = self.shell('''
        atlas_update_core_prepare() { echo core-prepare; }
        atlas_update_ingress_prepare() { echo writer-prepare; }
        atlas_update_sports_prepare() { echo controller-prepare; }
        atlas_update_core_apply() { echo core-apply; }
        atlas_update_ingress_apply() { echo writer-apply; }
        atlas_update_sports_apply() { echo controller-apply; }
        atlas_update_prepare_scope all && atlas_update_apply_scope all
        ''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            'core-prepare', 'writer-prepare', 'controller-prepare',
            'core-apply', 'writer-apply', 'controller-apply'])


if __name__ == '__main__':
    unittest.main()
