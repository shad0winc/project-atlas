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


class ArchiveWriterStagingTests(unittest.TestCase):
    def load_writer(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'isolated_archive_writer_packaging', ROOT / 'scripts/lib/sports-archive-writer.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_staging_copies_policy_module_and_exact_declared_sources(self):
        import hashlib
        import shutil
        import tempfile
        from types import SimpleNamespace
        module = self.load_writer()
        def copy_tree(source, target, directory, *, target_owner):
            self.assertEqual(target_owner, (__import__('os').geteuid(), __import__('os').getegid()))
            if directory:
                shutil.copytree(source, target)
            else:
                shutil.copyfile(source, target)
        synced = []
        native = SimpleNamespace(copy_tree=copy_tree, pub=SimpleNamespace(sync=synced.append))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'source'
            module.stage_source(native, target)
            self.assertEqual(set(item.name for item in target.iterdir()), set(module.source_inputs()))
            self.assertIn('atlas_live_policy_claim.py', module.source_inputs())
            for name, source in module.source_inputs().items():
                files = sorted(source.rglob('*')) if source.is_dir() else [source]
                for item in files:
                    if item.is_file():
                        destination = target / name / item.relative_to(source) if source.is_dir() else target / name
                        self.assertEqual(hashlib.sha256(destination.read_bytes()).digest(),
                                         hashlib.sha256(item.read_bytes()).digest())
            self.assertEqual(synced, [target])

    def assert_copy_contract_refused(self, dockerfile):
        import tempfile
        from types import SimpleNamespace
        module = self.load_writer()
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            declared = fixture / 'modules/sports/Dockerfile.private-api'
            declared.parent.mkdir(parents=True)
            declared.write_text(dockerfile)
            module.ROOT = fixture
            calls = []
            native = SimpleNamespace(copy_tree=lambda *args, **kwargs: calls.append(args),
                                     pub=SimpleNamespace(sync=lambda path: calls.append(path)))
            target = fixture / 'staged'
            with self.assertRaises(ValueError):
                module.stage_source(native, target)
            self.assertEqual(calls, [])
            self.assertFalse(target.exists())

    def test_missing_policy_copy_is_rejected_before_staging(self):
        text = (ROOT / 'modules/sports/Dockerfile.private-api').read_text()
        line = 'COPY modules/sports/src/atlas_live_policy_claim.py /srv/sports/atlas_live_policy_claim.py\n'
        self.assertEqual(text.count(line), 1)
        self.assert_copy_contract_refused(text.replace(line, ''))

    def test_unreviewed_extra_copy_is_rejected_before_staging(self):
        text = (ROOT / 'modules/sports/Dockerfile.private-api').read_text()
        self.assert_copy_contract_refused(text + '\nCOPY unreviewed.py /srv/sports/unreviewed.py\n')

if __name__ == '__main__':
    unittest.main()
