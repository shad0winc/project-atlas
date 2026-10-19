#!/usr/bin/env python3
"""Durable native publication primitives; no recovery release or admission policy.

Only status/current token writes and scheduler-source flushing are exposed. This
helper cannot decide that runtime, private or public acceptance has passed.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import sys
import tempfile


class DurabilityError(RuntimeError):
    pass


def directory(path: Path):
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise DurabilityError('Unsafe publication directory')
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise DurabilityError('Unsafe publication directory')
    return info


def regular(info):
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.geteuid() or info.st_mode & 0o022):
        raise DurabilityError('Unsafe publication file')


def sync_directory(path: Path):
    before = directory(path)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino):
            raise DurabilityError('Publication directory changed')
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_token(path: Path, value: str, *, checkpoint=lambda _: None):
    if path.name not in ('status', 'current') or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value) is None:
        raise DurabilityError('Invalid publication token')
    parent = path.parent
    parent_info = directory(parent)
    old = None
    try:
        old = path.lstat()
        regular(old)
    except FileNotFoundError:
        pass
    fd, staged = tempfile.mkstemp(prefix='.' + path.name + '.durable-', dir=parent)
    temporary = Path(staged)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), stat.S_IMODE(old.st_mode) if old is not None else 0o644)
            if old is not None and (old.st_uid, old.st_gid) != (os.geteuid(), os.getegid()):
                os.fchown(stream.fileno(), old.st_uid, old.st_gid)
            stream.write((value + '\n').encode('ascii'))
            stream.flush()
            os.fsync(stream.fileno())
        checkpoint('file_fsynced')
        now_parent = directory(parent)
        if (parent_info.st_dev, parent_info.st_ino) != (now_parent.st_dev, now_parent.st_ino):
            raise DurabilityError('Publication directory changed')
        try:
            now = path.lstat()
        except FileNotFoundError:
            now = None
        if old is None:
            if now is not None:
                raise DurabilityError('Publication target appeared')
        elif now is None or (now.st_dev, now.st_ino, now.st_size, now.st_mtime_ns, now.st_ctime_ns) != (
                old.st_dev, old.st_ino, old.st_size, old.st_mtime_ns, old.st_ctime_ns):
            raise DurabilityError('Publication target changed')
        os.replace(temporary, path)
        checkpoint('replaced')
        sync_directory(parent)
        checkpoint('directory_fsynced')
    finally:
        temporary.unlink(missing_ok=True)


def sync_generation(root: Path, environment: Path):
    """Flush files and directories, allowing only the native root .env link.

    This is durability, not source provenance verification. The native archive
    and mixed-runtime validators must run independently before publication.
    """
    directory(root)
    if not environment.is_absolute():
        raise DurabilityError('Invalid generation environment target')
    count = 0
    def descend(path: Path, depth: int):
        nonlocal count
        if depth > 64:
            raise DurabilityError('Generation depth limit exceeded')
        directory(path)
        for entry in sorted(path.iterdir()):
            count += 1
            if count > 20000:
                raise DurabilityError('Generation entry limit exceeded')
            before = entry.lstat()
            if stat.S_ISDIR(before.st_mode):
                descend(entry, depth + 1)
            elif stat.S_ISLNK(before.st_mode):
                if entry != root / '.env' or os.readlink(entry) != str(environment):
                    raise DurabilityError('Unexpected generation link')
                target = environment.lstat()
                if not stat.S_ISREG(target.st_mode) or target.st_mode & 0o022:
                    raise DurabilityError('Unsafe environment overlay target')
            else:
                regular(before)
                fd = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    opened = os.fstat(fd)
                    if opened != before:
                        raise DurabilityError('Generation file changed')
                    os.fsync(fd)
                    after = os.fstat(fd)
                    if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        raise DurabilityError('Generation file changed')
                finally:
                    os.close(fd)
        sync_directory(path)
    descend(root, 0)
    # Flush the containing namespace as well; a later rename still requires
    # the caller to flush the destination directory after that rename.
    sync_directory(root.parent)


def main(arguments):
    if len(arguments) == 3 and arguments[0] == 'write':
        atomic_token(Path(arguments[1]), arguments[2])
    elif len(arguments) == 3 and arguments[0] == 'generation':
        sync_generation(Path(arguments[1]), Path(arguments[2]))
    elif len(arguments) == 2 and arguments[0] == 'directory':
        sync_directory(Path(arguments[1]))
    else:
        raise DurabilityError('Invalid durable publication operation')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except (OSError, DurabilityError):
        print('ERROR: durable publication failed; retain maintenance and recovery ownership.', file=sys.stderr)
        raise SystemExit(1)
