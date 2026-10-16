"""Provision the canonical writer-private metadata directory without enabling refresh."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import shutil
import tempfile
import subprocess
import sys


def require(condition):
    if not condition:
        raise ValueError('Metadata runtime ownership, path or state contract failed')


def directory(path, uid, gid, *, create=False):
    # Reject symbolic ancestors before following a path. Existing directories are
    # validated, never recursively repaired or reassigned.
    require(path.is_absolute() and '..' not in path.parts)
    for parent in reversed((path, *path.parents)):
        if parent.exists() or parent.is_symlink():
            require(stat.S_ISDIR(parent.lstat().st_mode) and not parent.is_symlink())
    try:
        info = path.lstat()
    except FileNotFoundError:
        require(create)
        path.mkdir(mode=0o700)
        os.chown(path, uid, gid)
        info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == uid
            and info.st_gid == gid and stat.S_IMODE(info.st_mode) == 0o700)


def writer_identity(project):
    # Compose is the authority for image build PUID/PGID. Never source or print
    # operator environment files or the resolved Compose document.
    result = subprocess.run(
        ['docker', 'compose', '--env-file', str(project / '.env'),
         '-f', str(project / 'stack/ingress.yml'), 'config', '--format', 'json'],
        capture_output=True, timeout=30, check=False,
    )
    require(result.returncode == 0 and len(result.stdout) <= 4_000_000)
    args = json.loads(result.stdout)['services']['sports-writer']['build']['args']
    values = [str(args[key]) for key in ('PUID', 'PGID')]
    require(all(value.isascii() and value.isdigit() for value in values))
    uid, gid = map(int, values)
    require(0 < uid < 2**31 and 0 < gid < 2**31)
    return uid, gid


def check_state(root, uid, gid):
    directory(root, uid, gid)
    allowed = {'metadata.sqlite', 'metadata.sqlite.lock',
               'metadata.sqlite-journal', 'metadata.sqlite-wal', 'metadata.sqlite-shm'}
    entries = {path.name for path in root.iterdir()}
    require(entries <= allowed and {'metadata.sqlite', 'metadata.sqlite.lock'} <= entries)
    for name in entries:
        info = (root / name).lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and info.st_uid == uid and info.st_gid == gid
                and stat.S_IMODE(info.st_mode) == 0o600)


def validate_state(project, root, uid, gid):
    check_state(root, uid, gid)
    spec = importlib.util.spec_from_file_location(
        'atlas_metadata_recovery', project / 'scripts/lib/metadata-recovery.py')
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
    with recovery.source_lock(root / 'metadata.sqlite.lock', uid):
        recovery.validate_database(root / 'metadata.sqlite')


def provision_state(project, runtime, uid, gid):
    require(os.geteuid() in {0, uid})
    require(os.geteuid() == 0 or os.getegid() == gid)
    # Do not create a missing storage root, or follow symbolic ancestors.
    require(runtime.is_absolute() and runtime.is_dir())
    for parent in (runtime, *runtime.parents):
        require(not parent.is_symlink())
    private = runtime / 'private'
    directory(private, 0 if os.geteuid() == 0 else uid,
              0 if os.geteuid() == 0 else gid, create=True)
    root = private / 'sports-metadata'
    original = None
    if root.exists() or root.is_symlink():
        directory(root, uid, gid)
        original = root.stat().st_ino
        if any(root.iterdir()):
            # Never initialize, repair, chmod or chown existing records.
            validate_state(project, root, uid, gid)
            return
    # SQLite canonicalizes disk paths. Dropping UID inside a root-private host
    # parent cannot emulate the container's direct bind mount. Build NEW state
    # as the bootstrap identity, then assign only its newly created objects.
    stage = Path(tempfile.mkdtemp(prefix='.sports-metadata-new-', dir=private))
    try:
        sys.path.insert(0, str(project / 'modules/sports/src'))
        from providers.metadata_store import MetadataStore
        MetadataStore(stage / 'metadata.sqlite')
        validate_state(project, stage, os.geteuid(), os.getegid())
        for path in stage.iterdir():
            os.chown(path, uid, gid)
        os.chown(stage, uid, gid)
        check_state(stage, uid, gid)
        # A failed attempt's empty target may be retained. Do not replace a
        # changed target, link, nonempty directory or existing database.
        if original is not None:
            directory(root, uid, gid)
            require(root.stat().st_ino == original and not any(root.iterdir()))
        else:
            require(not root.exists() and not root.is_symlink())
        os.replace(stage, root)
    finally:
        # This unique staging directory contains only this attempt's NEW state.
        # Canonical state is never removed on failure.
        if stage.exists():
            shutil.rmtree(stage)
    validate_state(project, root, uid, gid)


def policy_helper(project):
    spec = importlib.util.spec_from_file_location(
        'atlas_metadata_policy', project / 'scripts/lib/sports-metadata-policy.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def provision_policy(project, runtime, uid, gid):
    helper = policy_helper(project)
    owner = 0 if os.geteuid() == 0 else uid
    private = runtime / 'private'
    directory(private, owner, 0 if owner == 0 else gid)
    root = private / 'sports-metadata-policy'
    if root.exists() or root.is_symlink():
        helper.read_directory(root, owner, gid)
        return
    stage = Path(tempfile.mkdtemp(prefix='.sports-metadata-policy-new-', dir=private))
    try:
        descriptor = os.open(stage / 'refresh.json',
                             os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(helper.DISABLED_POLICY)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(stage / 'refresh.json', owner, gid)
        os.chmod(stage / 'refresh.json', 0o640)
        os.chown(stage, owner, gid)
        os.chmod(stage, 0o750)
        helper.read_directory(stage, owner, gid)
        descriptor = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        # Do not replace a concurrent installation, even an empty directory.
        # A hard link cannot publish a directory; serialize canonical installers
        # with the existing update lock and refuse any observed target.
        require(not root.exists() and not root.is_symlink())
        os.rename(stage, root)
        descriptor = os.open(private, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    helper.read_directory(root, owner, gid)


def provision(project, runtime, uid, gid):
    provision_state(project, runtime, uid, gid)
    provision_policy(project, runtime, uid, gid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('provision',))
    parser.add_argument('project', type=Path)
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    provision(args.project, args.path, *writer_identity(args.project))
    print('SPORTS_METADATA_RUNTIME=PASS; REFRESH_POLICY=VALIDATED')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Compose output and private state never appear in deployment errors.
        print('ERROR: Sports metadata runtime provisioning failed; inspect ownership and state locally.', file=sys.stderr)
        raise SystemExit(1)
