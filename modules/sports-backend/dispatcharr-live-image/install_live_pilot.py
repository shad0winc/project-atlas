"""Install the default-off gate into one exact upstream settings file."""
from pathlib import Path
import ast, hashlib, sys

SETTINGS_SHA256 = 'de4cbe40fde55e1fe8f51324ab3a2a23c159d855652fea86ba12996e0b4fb5ea'
STATEMENT = '\nMIDDLEWARE = ["apps.m3u.live_pilot_gate.LiveSportsPilotMiddleware", *MIDDLEWARE]\n'

def install(root):
    path = root/'dispatcharr/settings.py'
    assert not path.is_symlink() and path.is_file()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() == SETTINGS_SHA256:
        tree = ast.parse(raw)
        matches = [n for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'MIDDLEWARE' for t in n.targets)]
        assert len(matches) == 1
        values = ast.literal_eval(matches[0].value)
        assert isinstance(values, (list, tuple)) and all(isinstance(v, str) for v in values)
        lines = raw.decode().splitlines(keepends=True)
        lines.insert(matches[0].end_lineno, STATEMENT)
        candidate = ''.join(lines).encode()
        ast.parse(candidate)
        path.write_bytes(candidate)
    else:
        # Verification is also idempotent, but accepts no other source edits.
        assert raw.count(STATEMENT.encode()) == 1
        original = raw.replace(STATEMENT.encode(), b'', 1)
        assert hashlib.sha256(original).hexdigest() == SETTINGS_SHA256
    print('LIVE_PILOT_SETTINGS_INSTALL_VERIFIED=true')

if __name__ == '__main__':
    install(Path(sys.argv[1]) if len(sys.argv)>1 else Path('/app'))
