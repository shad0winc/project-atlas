"""Cross-process metadata reuse and conservative admission; no extra provider calls.

Provider cooldown enforcement remains in the underlying transport. Only raw,
user-independent provider responses are cached. Imported by writer/controller.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import fcntl
import hashlib
import hmac
import json
import math
import os
import sqlite3
import stat
import time

MAX_ENTRIES = 128
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
TOTAL_PER_MINUTE = 20
BACKGROUND_PER_MINUTE = 12
BURST_PER_TEN_SECONDS = 4

class SharedRequestDeferred(RuntimeError):
    def __init__(self, seconds):
        self.retry_after_seconds = max(1, min(300, math.ceil(seconds)))
        super().__init__('Sports metadata request deferred')

class SharedResponseUnavailable(RuntimeError):
    pass

@dataclass(frozen=True)
class SharedReply:
    payload: dict
    observed_at: float

def finite_time(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid metadata clock')
    return float(value)

class SharedRequestCache:
    def __init__(self, root, credential, *, clock=time.time):
        self.root = Path(root)
        if not self.root.is_absolute() or '..' in self.root.parts:
            raise ValueError('Absolute cache directory required')
        if not isinstance(credential, str) or not credential:
            raise ValueError('Provider credential required')
        self.credential = credential
        self.clock = clock
        self.root.mkdir(mode=0o700, exist_ok=True)
        info = self.root.lstat()
        if (self.root.resolve(strict=True) != self.root or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Private owned metadata cache directory required')
        self.directory_identity = info.st_dev, info.st_ino
        self.database = self.root / 'cache.sqlite'
        descriptor = os.open(self.database, os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR | os.O_NONBLOCK, 0o600)
        try:
            row = os.fstat(descriptor)
            if (not stat.S_ISREG(row.st_mode) or row.st_uid != os.geteuid()
                    or row.st_nlink != 1 or stat.S_IMODE(row.st_mode) != 0o600):
                raise ValueError('Private owned metadata database required')
        finally:
            os.close(descriptor)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    observed REAL NOT NULL, ttl REAL NOT NULL, bytes INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS admissions (at REAL NOT NULL, background INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS failures (key TEXT PRIMARY KEY, until REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS clock (id INTEGER PRIMARY KEY, latest REAL NOT NULL);
            ''')

    def verify_directory(self):
        info = self.root.lstat()
        if ((info.st_dev, info.st_ino) != self.directory_identity or info.st_uid != os.geteuid()
                or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Metadata cache directory changed')

    @contextmanager
    def connect(self):
        self.verify_directory()
        db = sqlite3.connect(self.database, timeout=1)
        try:
            db.execute('PRAGMA synchronous=FULL')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def key(self, endpoint, parameters):
        if not isinstance(endpoint, str) or not isinstance(parameters, dict):
            raise ValueError('Invalid metadata identity')
        raw = json.dumps([endpoint, sorted(parameters.items())], separators=(',', ':'), allow_nan=False).encode()
        if len(raw) > 4096:
            raise ValueError('Metadata request identity too large')
        return hmac.new(self.credential.encode(), raw, hashlib.sha256).hexdigest()

    def now(self, db):
        now = finite_time(self.clock())
        prior = db.execute('SELECT latest FROM clock WHERE id=1').fetchone()
        if prior and now < prior[0]:
            raise SharedResponseUnavailable('Metadata clock regressed')
        db.execute('INSERT OR REPLACE INTO clock VALUES (1,?)', (now,))
        return now

    def lookup(self, db, key, now):
        row = db.execute('SELECT payload,observed,ttl FROM cache WHERE key=?', (key,)).fetchone()
        if row and 0 <= now-row[1] < row[2]:
            payload = json.loads(row[0])
            if not isinstance(payload, dict):
                raise SharedResponseUnavailable('Invalid cached metadata')
            return SharedReply(payload, row[1])
        return None

    def get_or_fetch(self, endpoint, parameters, *, ttl, background, fetch):
        if type(ttl) not in (int, float) or not math.isfinite(ttl) or not 0 < ttl <= 300:
            raise ValueError('Bounded metadata TTL required')
        if type(background) is not bool:
            raise ValueError('Explicit request class required')
        key = self.key(endpoint, parameters)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            now = self.now(db)
            reply = self.lookup(db, key, now)
            if reply is not None:
                return reply
        # Fixed lock stripes bound filesystem growth. A matching in-flight
        # request yields immediately rather than consuming another upstream hit.
        descriptor = os.open(self.root / ('fetch-%02d.lock' % (int(key[:4], 16) % 16)),
            os.O_CREAT | os.O_NOFOLLOW | os.O_RDWR | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
                raise ValueError('Unsafe metadata request lock')
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SharedRequestDeferred(1) from None
            self.verify_directory()
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                now = self.now(db)
                reply = self.lookup(db, key, now)
                if reply is not None:
                    return reply
                failure = db.execute('SELECT until FROM failures WHERE key=?', (key,)).fetchone()
                if failure and failure[0] > now:
                    raise SharedResponseUnavailable('Recent metadata fetch failed')
                db.execute('DELETE FROM admissions WHERE at<=?', (now-60,))
                db.execute('DELETE FROM failures WHERE until<=?', (now,))
                stamps = db.execute('SELECT at,background FROM admissions ORDER BY at').fetchall()
                waits = []
                if len(stamps) >= TOTAL_PER_MINUTE:
                    waits.append(stamps[0][0]+60-now)
                bg = [at for at,is_background in stamps if is_background]
                if background and len(bg) >= BACKGROUND_PER_MINUTE:
                    waits.append(bg[0]+60-now)
                burst = [at for at,_ in stamps if now-at < 10]
                if len(burst) >= BURST_PER_TEN_SECONDS:
                    waits.append(burst[0]+10-now)
                if waits:
                    raise SharedRequestDeferred(max(waits))
                db.execute('INSERT INTO admissions VALUES (?,?)', (now, int(background)))
            # Admission is durable before HTTP; no refund for errors or crashes.
            observed = now
            try:
                payload = fetch()
                if not isinstance(payload, dict):
                    raise ValueError('Metadata must be an object')
                raw = json.dumps(payload, separators=(',', ':'), allow_nan=False)
                size = len(raw.encode())
                if size > MAX_RESPONSE_BYTES:
                    raise ValueError('Metadata response too large')
            except Exception as error:
                # Never cache exception messages or provider response bodies.
                # Actual provider 429s retain the existing shared cooldown.
                if not getattr(error, 'provider_rate_limited', False):
                    with self.connect() as db:
                        until = self.now(db)+15
                        db.execute('INSERT OR REPLACE INTO failures VALUES (?,?)', (key,until))
                raise
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                now = self.now(db)
                db.execute('DELETE FROM cache WHERE observed+ttl<=?', (now,))
                # An expired response is never published with a renewed age.
                if now-observed >= ttl:
                    raise SharedResponseUnavailable('Metadata fetch exceeded freshness window')
                db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?)', (key,raw,observed,ttl,size))
                db.execute('DELETE FROM failures WHERE key=?', (key,))
                while True:
                    count,total = db.execute('SELECT count(*),coalesce(sum(bytes),0) FROM cache').fetchone()
                    if count <= MAX_ENTRIES and total <= MAX_TOTAL_BYTES:
                        break
                    db.execute('DELETE FROM cache WHERE key=(SELECT key FROM cache ORDER BY observed,key LIMIT 1)')
            return SharedReply(payload, observed)
        finally:
            os.close(descriptor)
