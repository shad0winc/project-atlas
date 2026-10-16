"""Explicitly constructed, private SQLite state for the inactive metadata broker."""
from contextlib import contextmanager
import fcntl
import math
import os
from pathlib import Path
import sqlite3
import stat
import time


class MetadataStoreError(RuntimeError):
    pass


class MetadataStore:
    def __init__(self, path, *, lock_timeout=12):
        self.path = Path(path)
        if not math.isfinite(lock_timeout) or not 0 < lock_timeout <= 30:
            raise ValueError('Invalid metadata lock timeout')
        self.lock_timeout = lock_timeout
        # Caller provisions an exclusive directory. Never chmod/chown a shared path.
        parent = self.path.parent
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or parent.is_symlink()
            or info.st_uid != os.geteuid() or info.st_mode & 0o077):
            raise MetadataStoreError('Metadata directory must be private and owned by the writer')
        with self.locked(), self.connection() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS metadata_schema (version INTEGER NOT NULL);
                INSERT INTO metadata_schema SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM metadata_schema);
            ''')
            versions = connection.execute('SELECT version FROM metadata_schema').fetchall()
            if versions != [(1,)]:
                raise MetadataStoreError('Unsupported metadata state schema')
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS metadata_cache (
                    route TEXT NOT NULL, day TEXT NOT NULL, payload TEXT NOT NULL,
                    observed REAL NOT NULL, expires REAL NOT NULL,
                    PRIMARY KEY(route, day));
                CREATE TABLE IF NOT EXISTS metadata_attempts (stamp REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata_holds (
                    key TEXT PRIMARY KEY, until_stamp REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata_aliases (
                    provider TEXT NOT NULL, route TEXT NOT NULL, event_id TEXT NOT NULL,
                    owner_provider TEXT NOT NULL, owner_route TEXT NOT NULL, owner_event_id TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    PRIMARY KEY(provider, route, event_id));
            ''')

    def _private_file(self, path):
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
            os.close(descriptor)
            raise MetadataStoreError('Unsafe metadata state file')
        return descriptor

    @contextmanager
    def locked(self):
        descriptor = self._private_file(str(self.path) + '.lock')
        deadline = time.monotonic() + self.lock_timeout
        try:
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise MetadataStoreError('Metadata writer is busy') from None
                    time.sleep(0.02)
            yield
        finally:
            os.close(descriptor)

    @contextmanager
    def connection(self):
        descriptor = self._private_file(self.path)
        os.close(descriptor)
        connection = sqlite3.connect(self.path, timeout=2)
        try:
            connection.execute('PRAGMA synchronous=FULL')
            with connection:
                yield connection
        finally:
            connection.close()
