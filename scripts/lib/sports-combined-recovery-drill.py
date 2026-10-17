"""Five-surface publication and disposable consumer copies; no live destinations."""
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
import tempfile

LIMIT = 2 * 1024**3
MEMBERS = ('dispatcharr-db', 'dispatcharr-jwt', 'teamarr-db', 'sports-metadata', 'sports-metadata-policy')
DIRECTORIES = {'dispatcharr-db', 'sports-metadata', 'sports-metadata-policy'}


def require(value):
    if not value: raise ValueError('combined-fixture-contract')


def load(name):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module); return module


def private_write(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def file_bytes(path, limit):
    for parent in (path, *path.parents): require(not parent.is_symlink())
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= limit)
        raw = stream.read(limit + 1); after = os.fstat(stream.fileno())
    require(len(raw) == before.st_size and (before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
            (after.st_size,after.st_mtime_ns,after.st_ctime_ns))
    return raw


def file_sha(path):
    h = hashlib.sha256(); size = 0
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= LIMIT)
        for raw in iter(lambda:stream.read(1024*1024),b''):
            size += len(raw); require(size <= info.st_size); h.update(raw)
        after = os.fstat(stream.fileno())
    require(size == info.st_size and (info.st_mtime_ns,info.st_ctime_ns) == (after.st_mtime_ns,after.st_ctime_ns))
    return h.hexdigest()


def tree_digest(path, directory=False):
    # Same byte framing as the publication journal. Root export helpers cannot
    # use its same-euid check, so require the explicit preparing identity here.
    entries = [path,*sorted(path.rglob('*'))] if directory else [path]
    require(len(entries) <= 100000); total = 0; result = hashlib.sha256()
    for entry in entries:
        for parent in (entry, *entry.parents): require(not parent.is_symlink())
        info = entry.lstat(); is_dir = stat.S_ISDIR(info.st_mode)
        require(info.st_uid == 1000 and info.st_gid == 1000
                and stat.S_IMODE(info.st_mode) == (0o700 if is_dir else 0o600))
        require(is_dir or stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        result.update(('.' if entry == path else entry.relative_to(path).as_posix()).encode()
                      + (b'\0d\0' if is_dir else b'\0f\0'))
        if is_dir: continue
        total += info.st_size; require(total <= LIMIT)
        fd = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            opened = os.fstat(stream.fileno()); require((opened.st_ino,opened.st_dev) == (info.st_ino,info.st_dev))
            read = 0
            for raw in iter(lambda:stream.read(1024*1024),b''):
                read += len(raw); require(read <= info.st_size); result.update(raw)
            after = os.fstat(stream.fileno())
            require(read == info.st_size and (after.st_mtime_ns,after.st_ctime_ns) == (info.st_mtime_ns,info.st_ctime_ns))
        result.update(b'\0')
    return result.hexdigest()


def collect(root):
    require(not any(root.iterdir()))
    root.chmod(0o700); os.chown(root,1000,1000)
    output = root/'collected'; output.mkdir(mode=0o700)
    for name, source, limit in (
        ('new-jwt',Path('/dispatch-source/jwt'),16384),
        ('old-jwt',Path('/dispatch-old/jwt'),16384),
        ('teamarr.db',Path('/team-source/atlas-teamarr-snapshot.db'),512*1024**2)):
        info = source.lstat()
        require(info.st_uid == 0 and info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o600)
        raw = file_bytes(source,limit); require(raw)
        path = output/name; private_write(path,raw); os.chown(path,1000,1000)
    os.chown(output,1000,1000)


def metadata(root, stamp, owner):
    root.mkdir(mode=0o700)
    from providers.metadata_store import MetadataStore
    from providers.metadata_identity import MetadataIdentityRegistry, SourceIdentity
    store = MetadataStore(root/'metadata.sqlite')
    MetadataIdentityRegistry(store).enroll_verified(
        SourceIdentity('thesportsdb','4391',owner),
        [SourceIdentity('espn','football/nfl','401872996')], evidence_sha256='a'*64)
    with store.locked(),store.connection() as connection:
        connection.execute('INSERT INTO metadata_attempts VALUES (?)',(stamp,))
    return root/'metadata.sqlite'


def check_metadata(root, stamp, owner):
    load('metadata-recovery').validate_database(root/'metadata.sqlite',immutable=True)
    with sqlite3.connect((root/'metadata.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True) as conn:
        require(conn.execute('SELECT stamp FROM metadata_attempts').fetchall() == [(float(stamp),)])
        require(conn.execute("SELECT owner_event_id FROM metadata_aliases WHERE provider='espn'").fetchall() == [(owner,)])


def mark_old_teamarr(path):
    connection=sqlite3.connect(path,timeout=1)
    try:
        require(connection.execute('PRAGMA journal_mode=DELETE').fetchone()==('delete',))
        connection.execute("UPDATE atlas_teamarr_probe SET marker='old-combined'")
        connection.commit()
    finally:connection.close()
    require(not any(path.with_name(path.name+suffix).exists() for suffix in ('-wal','-shm','-journal')))


def stage(root):
    pg=load('sports-postgres-prepare'); bundle=load('sports-recovery-bundle')
    association=load('sports-recovery-association'); pub=load('sports-recovery-publication')
    source=pg.directory(Path('/dispatch-source/db')); major,tools=pg.tools_for(source)
    require(major=='17'); env={'PATH':str(tools['pg_ctl'].parent)+':/usr/bin:/bin','HOME':'/tmp','TMPDIR':'/tmp','LANG':'C','LC_ALL':'C'}
    pg.cold_state(source,tools,env); original_hash=pg.cluster_digest(source)
    dump=Path('/dispatch-source/atlas-cold-copy.dump'); dump_hash=pg.archive_digest(dump)
    with tempfile.TemporaryDirectory(prefix='project-atlas-restore.',dir='/tmp') as staged, \
         tempfile.TemporaryDirectory(prefix='project-atlas-pg-prepare.',dir='/tmp') as native:
        staged=Path(staged); native=Path(native)
        private_write(staged/'RECOVERY_FORMAT',b'3\n')
        backend=staged/'backend-recovery'; backend.mkdir(mode=0o700)
        for directory in ('dispatcharr','teamarr'): (backend/directory).mkdir(mode=0o700)
        for old,new in ((dump,backend/'dispatcharr/database.dump'),
            (root/'collected/new-jwt',backend/'dispatcharr/jwt'),
            (root/'collected/teamarr.db',backend/'teamarr/teamarr.db')):
            pub.copy_file(old,new)
        private_write(backend/'MANIFEST.tsv',('surface\tarchive_path\tstatus\n'+''.join(
            surface+'\t'+path+'\tcaptured\n' for surface,path,_ in bundle.NATIVE)).encode())
        private_write(backend/'SHA256SUMS',''.join(file_sha(staged/path)+'  '+path+'\n'
            for _,path,_ in bundle.NATIVE).encode())
        m=staged/'metadata-recovery'; m.mkdir(mode=0o700)
        db=metadata(staged/'metadata-source',123,'2475454')
        pub.copy_file(db,m/'database.sqlite')
        new_policy=b'{\n  "version": 1,\n  "enabled": false\n}\n'
        private_write(m/'refresh-policy.json',new_policy)
        private_write(m/'MANIFEST.json',(json.dumps({'version':2,'database_schema':1,
            'database_sha256':file_sha(m/'database.sqlite'),'policy_sha256':file_sha(m/'refresh-policy.json')})+'\n').encode())
        prepared=bundle.prepare(staged,{'dispatcharr':[1000,1000],'dispatcharr_jwt':[0,0],
                                      'teamarr':[0,0],'writer':[1000,1000]})
        pg.copy_cluster(source,native/'cold-cluster'); pub.copy_file(dump,native/'database.dump')
        pg.prepare(native,database='atlas_cold_drill',admin_role='dispatch',dump_sha256=dump_hash)
        bound=association.associate(prepared,native,database='atlas_cold_drill',admin_role='dispatch')
        current=root/'current'; current.mkdir(mode=0o700)
        pg.copy_cluster(source,current/'dispatcharr-db')
        pub.copy_file(root/'collected/old-jwt',current/'dispatcharr-jwt')
        pub.copy_file(root/'collected/teamarr.db',current/'teamarr-db')
        mark_old_teamarr(current/'teamarr-db')
        metadata(current/'sports-metadata',111,'2475455')
        (current/'sports-metadata-policy').mkdir(mode=0o700)
        private_write(current/'sports-metadata-policy/refresh.json',b'{"version":1,"enabled":false}\n')
        pub.stage(bound,root); pub.apply(root)
        plan=pub.read_json(root/'transaction/PLAN.json')
        check_metadata(current/'sports-metadata',123,'2475454')
        private_write(root/'DRILL.json',(json.dumps({'version':1,'plan_sha256':file_sha(root/'transaction/PLAN.json'),
            'source_sha256':original_hash,'dump_sha256':dump_hash,
            'jwt_sha256':file_sha(current/'dispatcharr-jwt'),'surfaces':plan['surfaces']})+'\n').encode())
        # All staging inputs are disposable; recovery must not depend on them.
        shutil.rmtree(bound); shutil.rmtree(prepared.parent)
    pg.cold_state(source,tools,env)
    require(pg.cluster_digest(source)==original_hash and pg.archive_digest(dump)==dump_hash)


def receipt(root):
    info=(root/'DRILL.json').lstat()
    require(info.st_uid==1000 and info.st_gid==1000 and stat.S_IMODE(info.st_mode)==0o600)
    def unique(pairs):
        value={}
        for k,v in pairs: require(k not in value); value[k]=v
        return value
    value=json.loads(file_bytes(root/'DRILL.json',16384),object_pairs_hook=unique)
    require(set(value)=={'version','plan_sha256','source_sha256','dump_sha256','jwt_sha256','surfaces'}
            and type(value['version']) is int and value['version']==1)
    for key in ('plan_sha256','source_sha256','dump_sha256','jwt_sha256'):
        require(isinstance(value[key],str) and re.fullmatch('[a-f0-9]{64}',value[key]) is not None)
    require(file_sha(root/'transaction/PLAN.json')==value['plan_sha256'])
    require(isinstance(value['surfaces'],list) and len(value['surfaces'])==5)
    for name,row in zip(MEMBERS,value['surfaces']):
        require(set(row)=={'surface','old_sha256','new_sha256'} and row['surface']==name)
        require(all(isinstance(row[k],str) and re.fullmatch('[a-f0-9]{64}',row[k]) for k in ('old_sha256','new_sha256')))
    return value


def content_shape(path, directory=False):
    entries=[path,*sorted(path.rglob('*'))] if directory else [path]
    require(len(entries)<=100000);result={};total=0
    for entry in entries:
        info=entry.lstat();require(not stat.S_ISLNK(info.st_mode))
        name='.' if entry==path else entry.relative_to(path).as_posix()
        if stat.S_ISDIR(info.st_mode):result[name]=('directory',)
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink==1)
            total+=info.st_size;require(total<=LIMIT)
            result[name]=('file',info.st_size,file_sha(entry))
    return result


def copy_owned(source, target, uid, gid, directory=False, dmode=0o700, fmode=0o600):
    # Sources were fully validated before this routine. Destinations are new
    # entries in empty, host-attested disposable volume mounts only.
    before=content_shape(source,directory)
    if directory:
        target.mkdir(mode=0o700)
        for path in sorted(source.rglob('*'),key=lambda p:(len(p.parts),str(p))):
            destination=target/path.relative_to(source)
            if path.is_dir(): destination.mkdir(mode=0o700)
            else:
                with path.open('rb') as reader:
                    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                    with os.fdopen(fd,'wb') as writer:
                        shutil.copyfileobj(reader,writer,1024*1024); writer.flush(); os.fsync(writer.fileno())
        for path in [*sorted(target.rglob('*'),key=lambda p:-len(p.parts)),target]:
            path.chmod(dmode if path.is_dir() else fmode); os.chown(path,uid,gid)
    else:
        private_write(target,file_bytes(source,512*1024**2)); target.chmod(fmode); os.chown(target,uid,gid)
    require(content_shape(source,directory)==before and content_shape(target,directory)==before)


def materialize(root):
    value=receipt(root); current=root/'current'
    require({p.name for p in current.iterdir()}==set(MEMBERS))
    for row in value['surfaces']:
        require(tree_digest(current/row['surface'],row['surface'] in DIRECTORIES)==row['new_sha256'])
    for name in ('/dispatch-target','/team-target','/metadata-target'):
        path=Path(name); require(path.is_dir() and not path.is_symlink() and not any(path.iterdir()))
        path.chmod(0o755)
    copy_owned(current/'dispatcharr-db',Path('/dispatch-target/db'),1000,1000,True)
    copy_owned(current/'dispatcharr-jwt',Path('/dispatch-target/jwt'),0,0)
    copy_owned(current/'teamarr-db',Path('/team-target/teamarr.db'),0,0)
    copy_owned(current/'teamarr-db',Path('/team-target/atlas-teamarr-snapshot.db'),0,0)
    copy_owned(current/'sports-metadata',Path('/metadata-target/sports-metadata'),1000,1000,True)
    copy_owned(current/'sports-metadata-policy',Path('/metadata-target/sports-metadata-policy'),0,1000,True,0o750,0o640)
    for row in value['surfaces']:
        require(tree_digest(current/row['surface'],row['surface'] in DIRECTORIES)==row['new_sha256'])
    # Check bytes after ownership assignment without weakening journal validation.
    require(file_sha(Path('/dispatch-target/jwt'))==value['jwt_sha256'])


def probe(root):
    value=receipt(root)
    metadata_root=Path('/metadata-target/sports-metadata')
    for path in (metadata_root,metadata_root/'metadata.sqlite',metadata_root/'metadata.sqlite.lock'):
        info=path.lstat(); require(info.st_uid==1000 and info.st_gid==1000
                                 and stat.S_IMODE(info.st_mode)==(0o700 if path.is_dir() else 0o600))
    check_metadata(metadata_root,123,'2475454')
    policy=load('sports-metadata-policy').read_directory(Path('/metadata-target/sports-metadata-policy'),0,1000)
    require(load('sports-metadata-policy').validate_bytes(policy) is None)
    expected=next(row['new_sha256'] for row in value['surfaces'] if row['surface']=='sports-metadata-policy')
    # Parent metadata volume is RO; this is consumer readability, not worker startup.
    h=hashlib.sha256();h.update(b'.\0d\0');h.update(b'refresh.json\0f\0');h.update(policy);h.update(b'\0')
    require(h.hexdigest()==expected)


def verify_consumers(root):
    value=receipt(root); jwt=Path('/dispatch-target/jwt'); info=jwt.lstat()
    require(info.st_uid==0 and info.st_gid==0 and stat.S_IMODE(info.st_mode)==0o600
            and file_sha(jwt)==value['jwt_sha256'])
    pg=load('sports-postgres-prepare'); path=Path('/dispatch-target/db'); info=path.lstat()
    require(info.st_uid==1000 and info.st_gid==1000 and stat.S_IMODE(info.st_mode)==0o700)
    major,tools=pg.tools_for(path); require(major=='17')
    pg.cold_state(path,tools,{'TMPDIR':'/tmp','PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
    team=load('sports-teamarr-recovery-drill'); result=team.capture(Path('/team-target'),'after-dump')
    require(result['cold_set_unchanged'] and result['cold_set_valid'] and result['database_mode']=='0600')


def rollback(root):
    value=receipt(root); pub=load('sports-recovery-publication')
    pub.recover(root); pub.recover(root)
    require(pub.read_json(root/'transaction/STATUS.json')=={'state':'reverted'})
    for row in value['surfaces']:
        require(pub.digest(root/'current'/row['surface'],row['surface'] in DIRECTORIES)==row['old_sha256'])
    check_metadata(root/'current/sports-metadata',111,'2475455')
    pg=load('sports-postgres-prepare'); source=Path('/dispatch-source/db'); _,tools=pg.tools_for(source)
    pg.cold_state(source,tools,{'TMPDIR':'/tmp','PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
    require(pg.cluster_digest(source)==value['source_sha256']
            and pg.archive_digest(Path('/dispatch-source/atlas-cold-copy.dump'))==value['dump_sha256'])


def run(mode, sandbox):
    root=Path(sandbox)
    require(root.parent==Path('/tmp') and re.fullmatch('project-atlas-sports-publication\\.[a-f0-9]{32}',root.name))
    require(os.environ.get('ATLAS_COMBINED_DRILL')=='1')
    require(mode in {'collect','stage','materialize','probe','verify-consumers','rollback'})
    wanted=0 if mode in {'collect','materialize','verify-consumers'} else 1000
    require(os.geteuid()==wanted and os.getegid()==wanted)
    for parent in (root,*root.parents): require(not parent.is_symlink())
    if mode!='collect':
        info=root.lstat(); require(stat.S_ISDIR(info.st_mode) and info.st_uid==1000
                                  and info.st_gid==1000 and stat.S_IMODE(info.st_mode)==0o700)
    {'collect':collect,'stage':stage,'materialize':materialize,'probe':probe,
     'verify-consumers':verify_consumers,'rollback':rollback}[mode](root)
    return {'version':1,'scope':'synthetic-combined-sports','mode':mode,'checks_passed':True,
            'production_state_access':False,'live_restore_enabled':False}


def main():
    try:
        require(len(sys.argv)==3)
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'modules/sports/src'))
        print(json.dumps(run(sys.argv[1],sys.argv[2]),sort_keys=True)); return 0
    except Exception:
        print('COMBINED_FIXTURE_HELPER=FAIL',file=sys.stderr); return 1


if __name__=='__main__': raise SystemExit(main())
