"""Atlas-schema synthetic metadata changes within isolated native undo rehearsal."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'modules/sports/src'))
from providers.espn_metadata import LEAGUE_UIDS, parse_scoreboard
from providers.metadata_store import MetadataStore
from providers.metadata_identity import MetadataIdentityRegistry, SourceIdentity


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'scripts/lib'/(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


recovery = load('metadata-recovery')
policy = load('sports-metadata-policy')
POLICIES = {'old': b'{"version":1,"enabled":false}\n',
    'new': b'{\n  "version": 1,\n  "enabled": false\n}\n',
    'consumed': b'{\n    "version": 1,\n    "enabled": false\n}\n'}
OWNERS = {'old': '910001', 'new': '910002'}
ATTEMPTS = {'old': [111.0], 'new': [123.0], 'consumed': [123.0, 456.0]}


def require(value):
    if not value: raise ValueError('Isolated Atlas metadata consumption held')


def payload(generation):
    return {'events': [], 'leagues': [{'uid': LEAGUE_UIDS['football/nfl']}], 'fixture_generation': generation}


def alias(store, owner, event):
    # Synthetic identities and provenance, not real event evidence.
    MetadataIdentityRegistry(store).enroll_verified(SourceIdentity('thesportsdb', '4391', owner),
        [SourceIdentity('espn', 'football/nfl', event)], evidence_sha256='f'*64)


def write_policy(native, directory, generation):
    raw = POLICIES[generation]; require(policy.validate_bytes(raw) is None)
    path = directory/'refresh.json'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    native.pub.sync(directory)


def create(native, parent, generation):
    require(generation in {'old', 'new'})
    directory = parent/'sports-metadata'; directory.mkdir(mode=0o700)
    store = MetadataStore(directory/'metadata.sqlite')
    alias(store, OWNERS[generation], '401999991')
    stamp = ATTEMPTS[generation][0]
    with store.locked(), store.connection() as connection:
        connection.execute('INSERT INTO metadata_attempts VALUES (?)', (stamp,))
        connection.execute('INSERT INTO metadata_holds VALUES (?, ?)', ('espn:cooldown', stamp+30))
        connection.execute('INSERT INTO metadata_cache VALUES (?, ?, ?, ?, ?)',
            ('football/nfl', '2026-10-17', json.dumps(payload(generation)), stamp, stamp+60))
    native.pub.sync(directory)
    (parent/'sports-metadata-policy').mkdir(mode=0o700)
    write_policy(native, parent/'sports-metadata-policy', generation)
    check(native, parent, generation)


def check(native, parent, generation, *, reader=False):
    require(generation in {'old', 'new', 'consumed'})
    directory = parent/'sports-metadata'; policy_dir = parent/'sports-metadata-policy'
    before = native.pub.digest(directory, True)
    require({p.name for p in directory.iterdir()} == {'metadata.sqlite', 'metadata.sqlite.lock'}
        and (directory/'metadata.sqlite.lock').stat().st_size == 0)
    recovery.validate_database(directory/'metadata.sqlite', immutable=True)
    connection = sqlite3.connect((directory/'metadata.sqlite').as_uri()+'?mode=ro&immutable=1', uri=True)
    try:
        owner = SourceIdentity('thesportsdb', '4391', OWNERS['old' if generation == 'old' else 'new'])
        expected = [owner.values()+owner.values()+('f'*64,),
            SourceIdentity('espn', 'football/nfl', '401999991').values()+owner.values()+('f'*64,)]
        if generation == 'consumed':
            target = SourceIdentity('thesportsdb', '4391', '910003')
            expected += [target.values()+target.values()+('f'*64,),
                SourceIdentity('espn', 'football/nfl', '401999992').values()+target.values()+('f'*64,)]
        require(sorted(connection.execute('SELECT * FROM metadata_aliases').fetchall()) == sorted(expected))
        require(connection.execute('SELECT stamp FROM metadata_attempts ORDER BY stamp').fetchall() == [(v,) for v in ATTEMPTS[generation]])
        stamp = ATTEMPTS[generation][-1]
        require(connection.execute('SELECT key,until_stamp FROM metadata_holds').fetchall() == [('espn:cooldown', stamp+30)])
        rows = connection.execute('SELECT route,day,payload,observed,expires FROM metadata_cache').fetchall()
        require(len(rows) == 1 and rows[0][:2] == ('football/nfl', '2026-10-17')
            and json.loads(rows[0][2]) == payload(generation) and rows[0][3:] == (stamp, stamp+60))
        require(parse_scoreboard('football/nfl', json.loads(rows[0][2])) == ())
    finally: connection.close()
    if reader: raw = policy.read_directory(policy_dir, 0, 1000)
    else:
        native.pub.digest(policy_dir, True)
        require({p.name for p in policy_dir.iterdir()} == {'refresh.json'})
        raw = (policy_dir/'refresh.json').read_bytes()
    require(raw == POLICIES[generation] and policy.validate_bytes(raw) is None)
    require(native.pub.digest(directory, True) == before)


def initialize(native, sandbox):
    root = native.consumer.scoped(sandbox)
    with native.pub.locked(root):
        transaction, plan, state = native.pub.load(root)
        require(state == 'applied-awaiting-verification')
        for generation, parent in (('old', transaction/'old'), ('new', root/'current')):
            for name in ('sports-metadata', 'sports-metadata-policy'):
                native.pub.digest(parent/name, True); shutil.rmtree(parent/name)
            create(native, parent, generation)
        for row in plan['surfaces']:
            if row['surface'] in {'sports-metadata', 'sports-metadata-policy'}:
                row['old_sha256'] = native.pub.digest(transaction/'old'/row['surface'], True)
                row['new_sha256'] = native.pub.digest(root/'current'/row['surface'], True)
        native.pub.write_json(transaction/'PLAN.json', plan)
        native.pub.sync(transaction/'old'); native.pub.sync(root/'current')
    print('ATLAS_METADATA_BASELINES=PASS', flush=True)


def mutate(native, sandbox):
    with native.consumer.writer(sandbox) as current:
        check(native, current, 'new')
        store = MetadataStore(current/'sports-metadata/metadata.sqlite')
        alias(store, '910003', '401999992')
        with store.locked(), store.connection() as connection:
            connection.execute('INSERT INTO metadata_attempts VALUES (?)', (456.0,))
            connection.execute('UPDATE metadata_holds SET until_stamp=? WHERE key=?', (486.0, 'espn:cooldown'))
            connection.execute('UPDATE metadata_cache SET payload=?,observed=?,expires=?',
                (json.dumps(payload('consumed')), 456.0, 516.0))
        native.pub.sync(current/'sports-metadata')
        write_policy(native, current/'sports-metadata-policy', 'consumed')
        check(native, current, 'consumed')
    print('ATLAS_METADATA_CONSUMER_COMMITS=PASS', flush=True)


def reader_probe(native, parent, generation):
    require(os.geteuid() == 0 and os.getegid() == 0)
    # Preload parser imports before dropping identity in the child.
    check(native, parent, generation)
    with tempfile.TemporaryDirectory(prefix='project-atlas-metadata-reader.', dir='/tmp') as temporary:
        target = Path(temporary); target.chmod(0o750); os.chown(target, 0, 1000)
        native.copy_tree(parent/'sports-metadata', target/'sports-metadata', True, (0, 0), (1000, 1000))
        native.copy_tree(parent/'sports-metadata-policy', target/'sports-metadata-policy', True, (0, 0), (0, 1000))
        (target/'sports-metadata-policy').chmod(0o750); (target/'sports-metadata-policy/refresh.json').chmod(0o640)
        shapes = {name: native.shape(target/name, True) for name in ('sports-metadata', 'sports-metadata-policy')}
        child = os.fork()
        if child == 0:
            try:
                os.setgroups([]); os.setgid(1000); os.setuid(1000)
                require(os.getresuid() == (1000, 1000, 1000) and os.getresgid() == (1000, 1000, 1000) and os.getgroups() == [])
                check(native, target, generation, reader=True); os._exit(0)
            except BaseException: os._exit(1)
        deadline = time.monotonic()+15
        try:
            while True:
                pid, status = os.waitpid(child, os.WNOHANG)
                if pid: require(os.waitstatus_to_exitcode(status) == 0); break
                require(time.monotonic() < deadline); time.sleep(0.02)
        except BaseException:
            try: os.kill(child, signal.SIGKILL)
            except ProcessLookupError: pass
            try: os.waitpid(child, 0)
            except ChildProcessError: pass
            raise
        require(all(native.shape(target/name, True) == before for name, before in shapes.items()))


def verify(native, sandbox):
    root = native.consumer.scoped(sandbox)
    require(native.consumer.status(root/'consumption') == 'reverted')
    check(native, root/'current', 'old')
    check(native, root/'consumption/quarantine', 'consumed')
    reader_probe(native, root/'current', 'old')
    reader_probe(native, root/'consumption/quarantine', 'consumed')
    print('ATLAS_METADATA_ALIASES_BUDGET_POLICY_AND_UID1000_READER=PASS', flush=True)
