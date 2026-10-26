"""Keep the independent verified-live source suite in the core release gate."""
from pathlib import Path
import shutil
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class VerifiedLiveSourceGate(unittest.TestCase):
    def test_historical_and_head_contracts_pass_in_isolated_source_tree(self):
        result = subprocess.run(
            [sys.executable, '-B', str(ROOT / 'modules/sports-backend/dispatcharr-live-image/run-source-tests.py')],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DISPATCHARR_SOURCE_TESTS_PASSED=88', result.stdout)

    def test_cached_overlay_passes_but_unexpected_source_is_rejected(self):
        original = ROOT / 'modules/sports-backend/dispatcharr-live-image'
        with tempfile.TemporaryDirectory(prefix='atlas-overlay-cache-regression-') as tmp:
            copied = Path(tmp) / 'image'
            shutil.copytree(original, copied, ignore=shutil.ignore_patterns('__pycache__'))
            overlay = copied / 'overlay/apps/m3u'
            # Reproduce the bytecode side effect of importing during pytest collection.
            cache = overlay / '__pycache__/atlas_policy_claims.fixture.pyc'
            cache.parent.mkdir(exist_ok=True)
            cache.write_bytes(b'generated-cache-fixture')
            runner = copied / 'run-source-tests.py'
            def run():
                return subprocess.run([sys.executable, '-B', str(runner)],
                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
            result = run()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('DISPATCHARR_SOURCE_TESTS_PASSED=88', result.stdout)
            self.assertEqual(cache.read_bytes(), b'generated-cache-fixture')
            for unexpected in (overlay / 'unexpected.py', cache.parent / 'unexpected.py'):
                with self.subTest(path=str(unexpected.relative_to(copied))):
                    unexpected.write_text('# Unexpected source must fail the pinned inventory.\n')
                    try:
                        self.assertNotEqual(run().returncode, 0)
                    finally:
                        unexpected.unlink()


if __name__ == '__main__':
    unittest.main()
