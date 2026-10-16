"""Read and validate the fixed server-owned refresh policy; never enable it."""
import json
import os
from pathlib import Path
import stat
import sys

MAX_POLICY_BYTES = 16384
DISABLED_POLICY = b'{"version":1,"enabled":false}\n'


def require(condition):
    if not condition:
        raise ValueError('Invalid metadata policy storage')


def validate_bytes(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_POLICY_BYTES)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result
    # Use the worker's exact policy contract, including nominal request limits.
    project = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project / 'modules/sports/src'))
    from providers.metadata_refresh import parse_refresh_policy
    return parse_refresh_policy(json.loads(raw, object_pairs_hook=unique))


def read_directory(root, uid, gid):
    root = Path(root)
    require(root.is_absolute() and '..' not in root.parts)
    for part in (root, *root.parents):
        require(not part.is_symlink())
    info = root.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == uid
            and info.st_gid == gid and stat.S_IMODE(info.st_mode) == 0o750)
    require({path.name for path in root.iterdir()} == {'refresh.json'})
    descriptor = os.open(root / 'refresh.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and info.st_uid == uid and info.st_gid == gid
                and stat.S_IMODE(info.st_mode) == 0o640
                and 0 < info.st_size <= MAX_POLICY_BYTES)
        raw = handle.read(MAX_POLICY_BYTES + 1)
    validate_bytes(raw)
    return raw
