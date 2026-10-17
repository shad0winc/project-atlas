"""Real process-death rehearsal of cooperative filesystem consumer recovery.

Fixtures are explicit post-publication journal examples. Their PG/SQLite/JWT
payloads are synthetic filesystem state, not native application acceptance.
"""
import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

HEAD='57a2cfe5602449dbed069f4b11f9395093e79a20'
DEPLOYMENT='update-20261015T211211Z-632971'
PINS={'scripts/lib/sports-recovery-consumption.py': 'df7cc1d8897783db8073de033758f3012918a626f782df26263382b738600abd', 'scripts/lib/sports-recovery-publication.py': 'b0266e90b83ca297070aa98c563ae3fc98f674b46aa14f41357cc682b61d38c8'}
ROOT=Path(__file__).resolve().parents[2]


def load():
    for name,sha in PINS.items():
        path=ROOT/name
        assert path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    path=ROOT/'scripts/lib/sports-recovery-consumption.py'
    spec=importlib.util.spec_from_file_location('consumer_drill_journal',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


consumption=load() if PINS else None


def write(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def sqlite_fixture(path,marker):
    # This is a filesystem transaction fixture, not the native app schema.
    connection=sqlite3.connect(path)
    try:
        assert connection.execute('PRAGMA journal_mode=DELETE').fetchone()==('delete',)
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('CREATE TABLE probe(marker TEXT NOT NULL)')
        connection.execute('INSERT INTO probe VALUES (?)',(marker,));connection.commit()
    finally:connection.close()
    path.chmod(0o600)


def fixture(root):
    pub=consumption.publication
    (root/'current').mkdir(mode=0o700)
    transaction=root/'transaction';transaction.mkdir(mode=0o700)
    for name in ('incoming','old'):(transaction/name).mkdir(mode=0o700)
    for generation,parent in (('old',transaction/'old'),('new',root/'current')):
        for name in pub.SURFACES:
            path=parent/name
            if name in pub.DIRECTORIES:path.mkdir(mode=0o700)
        write(parent/'dispatcharr-db/state.bin',(generation+'-filesystem-pg-fixture').encode())
        write(parent/'dispatcharr-jwt',(generation+'-filesystem-identity-fixture').encode())
        sqlite_fixture(parent/'teamarr-db',generation+'-teamarr-fixture')
        sqlite_fixture(parent/'sports-metadata/metadata.sqlite',generation+'-metadata-fixture')
        write(parent/'sports-metadata/metadata.sqlite.lock',b'')
        policy=b'{"version":1,"enabled":false}\n' if generation=='old' else b'{\n  "version":1,\n  "enabled":false\n}\n'
        write(parent/'sports-metadata-policy/refresh.json',policy)
    rows=[{'surface':name,'old_sha256':pub.digest(transaction/'old'/name,name in pub.DIRECTORIES),
           'new_sha256':pub.digest(root/'current'/name,name in pub.DIRECTORIES)} for name in pub.SURFACES]
    pub.write_json(transaction/'PLAN.json',{'version':1,'scope':'isolated-only','ready_for_live_apply':False,
        'association_root':'/tmp/synthetic-journal-fixture-no-native-association',
        'association_sha256':'a'*64,'surfaces':rows})
    pub.write_json(transaction/'STATUS.json',{'state':'applied-awaiting-verification'})
    pub.sync(transaction/'old');pub.sync(transaction);pub.sync(root/'current');pub.sync(root)
    return rows


def mutate(root):
    with consumption.writer(root) as current:
        path=current/'dispatcharr-db/state.bin'
        with path.open('ab') as stream:stream.write(b'-consumer-write');stream.flush();os.fsync(stream.fileno())
        path=current/'dispatcharr-jwt'
        with path.open('ab') as stream:stream.write(b'-consumer-rotation');stream.flush();os.fsync(stream.fileno())
        for path in (current/'teamarr-db',current/'sports-metadata/metadata.sqlite'):
            connection=sqlite3.connect(path,timeout=1)
            try:
                connection.execute('PRAGMA synchronous=FULL')
                connection.execute("UPDATE probe SET marker='consumer-committed'");connection.commit()
            finally:connection.close()
        policy=current/'sports-metadata-policy/refresh.json'
        with policy.open('wb') as stream:
            stream.write(b'{\n      "version": 1,\n      "enabled": false\n}\n');stream.flush();os.fsync(stream.fileno())


def child_recover(root,boundary):
    def die(name):
        if name==boundary:os._exit(86)
    consumption.checkpoint=die
    if boundary=='opened':consumption.arm(root)
    else:consumption.recover(root)
    os._exit(0)


def verify(root,original):
    pub=consumption.publication
    assert pub.read_json(root/'consumption/STATUS.json')=={'state':'reverted'}
    seal=pub.read_json(root/'consumption/SEAL.json')
    assert len(seal['surfaces'])==5
    for row,sealed in zip(original,seal['surfaces']):
        name=row['surface'];is_dir=name in pub.DIRECTORIES
        assert pub.digest(root/'current'/name,is_dir)==row['old_sha256']
        assert pub.digest(root/'consumption/quarantine'/name,is_dir)==sealed['consumed_sha256']
    assert not any((root/'transaction/old').iterdir())
    assert not any((root/'transaction/incoming').iterdir())


def run_cases():
    ctx=multiprocessing.get_context('fork');pub=consumption.publication
    boundaries=['opened','sealing','seal-written','sealed','rolling-back',
        *['quarantine:'+name for name in pub.SURFACES],
        *['restore:'+name for name in pub.SURFACES],'reverted']
    for boundary in boundaries:
        with tempfile.TemporaryDirectory(prefix='project-atlas-sports-publication.',dir='/tmp') as temporary:
            root=Path(temporary);original=fixture(root)
            if boundary!='opened':
                consumption.arm(root);mutate(root)
                for row in original:
                    assert pub.digest(root/'current'/row['surface'],row['surface'] in pub.DIRECTORIES)!=row['new_sha256']
            process=ctx.Process(target=child_recover,args=(root,boundary));process.start();process.join(10)
            if process.is_alive():process.kill();process.join(2);raise RuntimeError('Child deadline')
            assert process.exitcode==86,(boundary,process.exitcode)
            consumption.recover(root);consumption.recover(root);verify(root,original)
        print('CONSUMER_RECOVERY_PROCESS_DEATH=PASS boundary='+boundary,flush=True)
    return len(boundaries)


def main():
    try:
        assert consumption is not None
        def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True,timeout=30)
        assert git('rev-parse','HEAD').strip()==HEAD
        assert git('-C','/opt/project-atlas','rev-parse','HEAD').strip()==HEAD
        assert not git('-C','/opt/project-atlas','status','--porcelain=v1')
        pointer=Path('/mnt/storage/configs/atlas/deployments/current')
        assert pointer.is_file() and not pointer.is_symlink()
        before=pointer.read_bytes();assert before.decode().strip()==DEPLOYMENT
        try:count=run_cases()
        finally:
            assert pointer.read_bytes()==before
            assert not git('-C','/opt/project-atlas','status','--porcelain=v1')
        print(json.dumps({'version':1,'scope':'synthetic-cooperative-filesystem-journal',
            'process_death_boundaries':count,'old_state_restored':True,'modified_state_quarantined':True,
            'production_state_access':False,'live_restore_enabled':False},sort_keys=True))
        print('COOPERATIVE_CONSUMER_RECOVERY_DRILL=PASS')
        print('STATE=isolated-journal-only-not-native-app-acceptance-not-deployed')
        return 0
    except Exception:
        print('COOPERATIVE_CONSUMER_RECOVERY_DRILL=FAIL',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
