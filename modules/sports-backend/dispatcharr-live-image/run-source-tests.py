"""Run isolated source tests with standard-library Python; no image or network."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_bytes())
    # Test collection and compile steps can create caches beside pinned source.
    # Ignore only regular bytecode in __pycache__; retain exact source inventory.
    actual = set()
    for path in (ROOT / 'overlay').rglob('*'):
        assert not path.is_symlink(), 'Overlay symlinks are not supported'
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT / 'overlay')
        if '__pycache__' in relative.parts and path.suffix == '.pyc':
            continue
        actual.add(str(relative))
    assert actual == set(manifest['overlay_files'])
    for name, expected in manifest['overlay_files'].items():
        path = ROOT / 'overlay' / name
        assert not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    for name, expected in manifest['test_files'].items():
        path = ROOT / name
        assert path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    with tempfile.TemporaryDirectory(prefix='atlas-dispatcharr-source-') as temporary:
        folder = Path(temporary)
        shutil.copytree(ROOT / 'overlay/apps', folder / 'apps',
                        ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / 'tests', folder / 'tests')
        for name in ('Dockerfile', 'manifest.json', '.dockerignore', 'test_stream_head.py', 'install_live_pilot.py'):
            shutil.copyfile(ROOT / name, folder / name)
        harness = '''import sys,unittest
suite=unittest.defaultTestLoader.discover(sys.argv[1],pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=1).run(suite)
assert result.testsRun==79,(result.testsRun, 'Expected all historical and HEAD tests')
assert not result.skipped, 'Source tests must not be skipped'
raise SystemExit(not result.wasSuccessful())
'''
        result = subprocess.run([sys.executable, '-B', '-c', harness, str(folder / 'tests')],
                                cwd=folder, timeout=90, stdin=subprocess.DEVNULL,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        if result.returncode:
            raise SystemExit(result.returncode)
    print('DISPATCHARR_SOURCE_TESTS_PASSED=79')


if __name__ == '__main__':
    main()
