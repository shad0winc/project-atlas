"""Keep the writer image importable and legacy positional source calls stable."""
from pathlib import Path
import ast
from dataclasses import fields
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'modules/sports/src'
sys.path.insert(0, str(SRC))
from source_lifecycle import SportsSource

class WriterPolicyPackagingTests(unittest.TestCase):
    def test_top_level_local_writer_imports_are_packaged(self):
        copies = {}
        for line in (ROOT / 'modules/sports/Dockerfile.private-api').read_text().splitlines():
            words = line.split()
            if words and words[0] == 'COPY' and len(words) == 3:
                copies[words[1]] = words[2]
        tree = ast.parse((SRC / 'private_api.py').read_text())
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                relative = node.module.replace('.', '/')
                local = SRC / (relative + '.py')
                if local.is_file():
                    source = str(local.relative_to(ROOT))
                    targets = [copies[source]] if source in copies else []
                    for origin, destination in copies.items():
                        directory = ROOT / origin
                        if directory.is_dir() and local.is_relative_to(directory):
                            targets.append(str(Path(destination) / local.relative_to(directory)))
                    with self.subTest(module=node.module):
                        self.assertIn('/srv/sports/' + relative + '.py', targets)
        self.assertIn('modules/sports/src/atlas_live_policy_claim.py', copies)

    def test_realm_does_not_shift_legacy_positional_arguments(self):
        legacy = (
            'source_id', 'display_name', 'kind', 'trust_class', 'enabled',
            'priority', 'max_connections', 'provider_id', 'provider_display_name',
            'account_display_name', 'backend_reference', 'purchased_at',
            'expires_at', 'renewal_url', 'renewal_notice_days',
        )
        self.assertEqual(tuple(field.name for field in fields(SportsSource)),
                         legacy + ('credential_realm',))
        source = SportsSource('source', 'Source', 'licensed_subscription',
                              'licensed', False, 100, 1, 'provider',
                              'Provider display', 'Account display')
        self.assertEqual(source.provider_display_name, 'Provider display')
        self.assertEqual(source.account_display_name, 'Account display')
        self.assertIsNone(source.credential_realm)

if __name__ == '__main__':
    unittest.main()
