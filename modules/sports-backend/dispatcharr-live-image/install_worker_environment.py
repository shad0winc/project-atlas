"""Preserve exact Atlas settings through the upstream login-shell launches."""
from pathlib import Path
import hashlib
import sys

ENTRYPOINT_SHA256 = '2c96dd61a1999654e32ac7b60999d0b9af196cded50952e4650f8530df426ceb'
ENVIRONMENT_KEYS = (
    'ATLAS_SPORTS_PILOT_MODE',
    'ATLAS_VERIFIED_LIVE_MODE',
    'ATLAS_RESERVATION_LEDGER_MIGRATED',
    'ATLAS_SPORTS_POLICY_ORIGIN',
    'ATLAS_SPORTS_LIVE_POLICY_TOKEN',
    'ATLAS_VERIFIED_LIVE_SCOPE_KEY_FILE',
)
LOGIN_ARGUMENTS = '--login --whitelist-environment=' + ','.join(ENVIRONMENT_KEYS)
CALLS = (
    ('su - "$POSTGRES_USER" -c "cd /app && python manage.py ', 2),
    ('su - "$POSTGRES_USER" -c "ulimit -n $DISPATCHARR_NOFILE ', 1),
)

def patched(original):
    assert hashlib.sha256(original).hexdigest() == ENTRYPOINT_SHA256, 'Upstream entrypoint drift'
    source = original.decode('utf-8')
    for before, count in CALLS:
        assert source.count(before) == count
        source = source.replace(before, before.replace('su - ', 'su ' + LOGIN_ARGUMENTS + ' ', 1))
    return source.encode()

def install(root):
    path = root / 'docker/entrypoint.sh'
    assert path.is_file() and not path.is_symlink(), 'Entrypoint unavailable'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() == ENTRYPOINT_SHA256:
        path.write_bytes(patched(raw))
    else:
        candidate = raw.decode('utf-8')
        for before, count in CALLS:
            after = before.replace('su - ', 'su ' + LOGIN_ARGUMENTS + ' ', 1)
            assert candidate.count(after) == count
            candidate = candidate.replace(after, before)
        assert hashlib.sha256(candidate.encode()).hexdigest() == ENTRYPOINT_SHA256, 'Installed entrypoint drift'
        assert patched(candidate.encode()) == raw
    print('ATLAS_WORKER_ENVIRONMENT_INSTALL_VERIFIED=true')

if __name__ == '__main__':
    install(Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/app'))
