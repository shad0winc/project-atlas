"""Private, consistent metadata recovery artifacts; never applies live state."""
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import tarfile
import tempfile
import time

MAX_DATABASE_BYTES = 512 * 1024 * 1024
EXPECTED_COLUMNS = {
    'metadata_schema': ('version',),
    'metadata_cache': ('route','day','payload','observed','expires'),
    'metadata_attempts': ('stamp',),
    'metadata_holds': ('key','until_stamp'),
    'metadata_aliases': ('provider','route','event_id','owner_provider','owner_route','owner_event_id','evidence'),
}
ROUTES = {'football/nfl','basketball/nba','baseball/mlb','hockey/nhl','soccer/eng.1','mma/ufc'}


class RecoveryError(ValueError):
    pass


def require(condition):
    if not condition:
        raise RecoveryError('Invalid metadata recovery state')


def safe_path(path):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts)
    for part in (path,*path.parents):
        require(not part.is_symlink())
    return path


def regular(path, *, uid=None):
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o600)
    require(uid is None or info.st_uid==uid)
    return info


def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as handle:
        for raw in iter(lambda:handle.read(1024*1024),b''):
            result.update(raw)
    return result.hexdigest()


def source_identity(provider,route,event_id):
    require(provider in {'espn','thesportsdb'})
    require(isinstance(event_id,str) and re.fullmatch(r'[0-9]{1,32}',event_id))
    require(route in ROUTES if provider=='espn' else
            isinstance(route,str) and re.fullmatch(r'[0-9]{1,32}',route))


def validate_database(path, *, immutable=False):
    require(0 < regular(path).st_size <= MAX_DATABASE_BYTES)
    uri=path.as_uri()+'?mode=ro'+('&immutable=1' if immutable else '')
    connection=sqlite3.connect(uri,uri=True,timeout=1)
    deadline=time.monotonic()+10
    connection.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
    try:
        require(connection.execute('PRAGMA quick_check').fetchall()==[('ok',)])
        definitions=connection.execute("SELECT type,name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'").fetchall()
        require({name for kind,name in definitions if kind=='table'}==set(EXPECTED_COLUMNS))
        require(all(kind in {'table','index'} for kind,name in definitions))
        for table,columns in EXPECTED_COLUMNS.items():
            require(tuple(row[1] for row in connection.execute('PRAGMA table_info('+table+')'))==columns)
        require(connection.execute('SELECT version FROM metadata_schema').fetchall()==[(1,)])
        require(connection.execute('SELECT provider,route,event_id FROM metadata_aliases GROUP BY provider,route,event_id HAVING COUNT(*)>1').fetchone() is None)
        for count,row in enumerate(connection.execute('SELECT * FROM metadata_aliases'),1):
            require(count<=100_000)
            provider,route,event_id,owner_provider,owner_route,owner_event_id,evidence=row
            source_identity(provider,route,event_id)
            source_identity(owner_provider,owner_route,owner_event_id)
            require(isinstance(evidence,str) and re.fullmatch('[a-f0-9]{64}',evidence))
            owner=connection.execute('SELECT owner_provider,owner_route,owner_event_id FROM metadata_aliases WHERE provider=? AND route=? AND event_id=?',
                (owner_provider,owner_route,owner_event_id)).fetchone()
            require(owner==(owner_provider,owner_route,owner_event_id))
    finally:
        connection.close()


@contextmanager
def source_lock(path,uid,*,timeout=12):
    regular(path,uid=uid)
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==uid and stat.S_IMODE(info.st_mode)==0o600)
        deadline=time.monotonic()+timeout
        while True:
            try:
                fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                require(time.monotonic()<deadline)
                time.sleep(.02)
        yield
    finally:
        os.close(descriptor)


def policy_helper():
    spec = importlib.util.spec_from_file_location(
        'atlas_metadata_policy', Path(__file__).with_name('sports-metadata-policy.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture(source,destination):
    source=safe_path(source);destination=safe_path(destination)
    # An absent installation stays absent. A present but incomplete installation
    # fails; it must never silently downgrade a backup to the previous format.
    policy = source.parent / 'sports-metadata-policy'
    if not source.exists():
        require(not policy.exists() and not policy.is_symlink())
        return False
    info=source.lstat()
    require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode)==0o700)
    require(destination.parent.is_dir() and not destination.exists())
    require(stat.S_IMODE(destination.parent.stat().st_mode)==0o700)
    database=source/'metadata.sqlite'
    require(0 < regular(database,uid=info.st_uid).st_size <= MAX_DATABASE_BYTES)
    for extra in source.iterdir():
        require(extra.name in {'metadata.sqlite','metadata.sqlite.lock','metadata.sqlite-journal','metadata.sqlite-wal','metadata.sqlite-shm'})
        regular(extra,uid=info.st_uid)
    # The policy is an independently captured configuration observation, not an
    # assertion that an in-flight request used this generation. No worker is stopped.
    policy_raw = None
    if policy.exists() or policy.is_symlink():
        policy_raw = policy_helper().read_directory(
            policy, 0 if os.geteuid() == 0 else os.geteuid(), info.st_gid)
    with source_lock(source/'metadata.sqlite.lock',info.st_uid):
        work=Path(tempfile.mkdtemp(prefix='.metadata-recovery-',dir=destination.parent))
        try:
            target=work/'database.sqlite'
            descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            os.close(descriptor)
            src=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=1)
            try:
                require(src.execute('PRAGMA page_count').fetchone()[0] * src.execute('PRAGMA page_size').fetchone()[0] <= MAX_DATABASE_BYTES)
                dst=sqlite3.connect(target)
                deadline=time.monotonic()+8
                def progress(status,remaining,total):
                    require(time.monotonic()<=deadline)
                try:
                    src.backup(dst,pages=128,progress=progress,sleep=.02)
                    # Produce one detached database even when the source uses WAL.
                    require(dst.execute('PRAGMA journal_mode=DELETE').fetchone()==('delete',))
                finally:
                    dst.close()
            finally:
                src.close()
            validate_database(target)
            manifest={'version':1,'database_schema':1,'database_sha256':digest(target)}
            if policy_raw is not None:
                descriptor=os.open(work/'refresh-policy.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(descriptor,'wb') as handle:
                    handle.write(policy_raw)
                manifest.update(version=2,policy_sha256=digest(work/'refresh-policy.json'))
            descriptor=os.open(work/'MANIFEST.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w') as handle:
                json.dump(manifest,handle,sort_keys=True)
                handle.write('\n')
            validate_staged(work)
            os.rename(work,destination)
        finally:
            if work.exists():shutil.rmtree(work)
    return True


def validate_staged(root):
    root=safe_path(root)
    require(root.is_dir() and stat.S_IMODE(root.stat().st_mode)==0o700)
    manifest_path=root/'MANIFEST.json';database=root/'database.sqlite'
    require(regular(manifest_path).st_size<=4096)
    regular(database)
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result);result[key]=value
        return result
    data=json.loads(manifest_path.read_bytes(),object_pairs_hook=unique)
    require(isinstance(data,dict) and type(data.get('version')) is int)
    require(data['version'] in {1,2})
    fields={'version','database_schema','database_sha256'}
    names={'MANIFEST.json','database.sqlite'}
    if data['version']==2:
        fields.add('policy_sha256');names.add('refresh-policy.json')
    require(set(data)==fields)
    require({path.name for path in root.iterdir()}==names)
    if data['version']==2:
        policy=root/'refresh-policy.json'
        require(0<regular(policy).st_size<=16384)
        require(data['policy_sha256']==digest(policy))
        policy_helper().validate_bytes(policy.read_bytes())
    require(type(data['database_schema']) is int and data['database_schema']==1)
    require(data['database_sha256']==digest(database))
    validate_database(database)


def validate_archive(path):
    require(Path(path).is_file() and not Path(path).is_symlink())
    with tarfile.open(path,'r:gz') as archive,tempfile.TemporaryDirectory(prefix='atlas-metadata-recovery-') as temporary:
        root=Path(temporary)
        seen=set()
        for member in archive.getmembers():
            name=member.name.rstrip('/')
            if not (name=='metadata-recovery' or name.startswith('metadata-recovery/')):
                continue
            require(name not in seen);seen.add(name)
            if name=='metadata-recovery':
                require(member.isdir() and member.mode==0o700)
                continue
            require(name in {'metadata-recovery/MANIFEST.json','metadata-recovery/database.sqlite','metadata-recovery/refresh-policy.json'})
            require(member.isfile() and member.mode==0o600)
            limit=4096 if name.endswith('MANIFEST.json') else 16384 if name.endswith('refresh-policy.json') else MAX_DATABASE_BYTES
            require(0<member.size<=limit)
            target=root/Path(name).name
            descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as out,archive.extractfile(member) as source:
                shutil.copyfileobj(source,out,length=1024*1024)
            require(target.stat().st_size==member.size)
        require({'metadata-recovery/MANIFEST.json','metadata-recovery/database.sqlite'}<=seen)
        validate_staged(root)


def main():
    try:
        operation=sys.argv[1]
        if operation=='capture' and len(sys.argv)==4:
            capture(Path(sys.argv[2]),Path(sys.argv[3]))
        elif operation=='validate-staged' and len(sys.argv)==3:
            validate_staged(Path(sys.argv[2])/'metadata-recovery')
        elif operation=='validate-archive' and len(sys.argv)==3:
            validate_archive(sys.argv[2])
        else:
            raise RecoveryError('Invalid recovery operation')
    except (RecoveryError,OSError,ValueError,sqlite3.Error,tarfile.TarError):
        print('ERROR: metadata recovery capture or validation failed.',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
