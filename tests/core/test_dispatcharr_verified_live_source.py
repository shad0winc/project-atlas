"""Keep the independent verified-live source suite in the core release gate."""
from pathlib import Path
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
        self.assertIn('DISPATCHARR_SOURCE_TESTS_PASSED=66', result.stdout)


if __name__ == '__main__':
    unittest.main()
