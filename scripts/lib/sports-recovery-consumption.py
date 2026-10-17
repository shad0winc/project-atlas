"""Fence cooperative private fixture writers, seal changed state and undo durably.

Only /tmp/project-atlas-sports-publication.* is accepted. This is not a Docker
stop barrier, native database validation, production ownership or live restore.
"""
from contextlib import contextmanager
import fcntl
import importlib.util
import os
from pathlib import Path
import re

_spec = importlib.util.spec_from_file_location('consumption_publication',
    Path(__file__).with_name('sports-recovery-publication.py'))
publication = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(publication)


class ConsumptionError(ValueError):
    pass


def require(value):
    if not value: raise ConsumptionError('Invalid isolated consumer recovery transaction')


def checkpoint(name):
    """No-op seam for real process death after durable mutation boundaries."""


def scoped(sandbox):
    root = Path(sandbox)
    require(root.parent == Path('/tmp') and re.fullmatch(
        r'project-atlas-sports-publication\.[A-Za-z0-9_-]+', root.name) is not None)
    publication.private(root, True)
    return root


@contextmanager
def file_lock(path, shared=False):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = publication.private(path)
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino, opened.st_nlink) == (info.st_dev, info.st_ino, 1))
        fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        # Do not act through a lock whose pathname was replaced while opening.
        current = publication.private(path)
        require((current.st_dev,current.st_ino) == (opened.st_dev,opened.st_ino))
        yield
    finally: os.close(fd)


@contextmanager
def journal(root):
    # The same publication lock protects both APIs. The legacy public context
    # deliberately refuses the consumption marker, so this private context adds
    # the new journal's own validation rather than bypassing legacy operations.
    with file_lock(root / 'publication.lock'):
        publication.private(root / 'current', True)
        require({p.name for p in (root/'current').iterdir()} <= set(publication.SURFACES))
        yield


def document_sha(path):
    return publication.digest(path)


def status(directory):
    value = publication.read_json(directory/'STATUS.json')
    require(isinstance(value,dict) and set(value)=={'state'} and value['state'] in {
        'open','sealing','sealed','rolling-back','reverted'})
    return value['state']


def set_status(directory,state):
    publication.write_json(directory/'STATUS.json',{'state':state})


def load(root):
    transaction,plan,original_state = publication.load(root)
    require(original_state=='applied-awaiting-verification')
    directory=root/'consumption';publication.private(directory,True)
    require({p.name for p in directory.iterdir()} <= {
        'EXPOSURE.json','STATUS.json','SEAL.json','quarantine',
        '.STATUS.json.writing','.SEAL.json.writing'})
    publication.private(directory/'quarantine',True)
    require(directory.stat().st_dev==(root/'current').stat().st_dev
        and (directory/'quarantine').stat().st_dev==(root/'current').stat().st_dev)
    require({p.name for p in (directory/'quarantine').iterdir()} <= set(publication.SURFACES))
    exposure=publication.read_json(directory/'EXPOSURE.json')
    require(isinstance(exposure,dict) and set(exposure)=={
        'version','scope','ready_for_live_apply','publication_plan_sha256','publication_status_sha256','surfaces'})
    require(type(exposure['version']) is int and exposure['version']==1
        and exposure['scope']=='isolated-cooperative-consumers' and exposure['ready_for_live_apply'] is False)
    require(exposure['publication_plan_sha256']==document_sha(transaction/'PLAN.json')
        and exposure['publication_status_sha256']==document_sha(transaction/'STATUS.json')
        and exposure['surfaces']==plan['surfaces'])
    return transaction,directory,exposure,status(directory)


def old_intact(root,transaction,exposure):
    require(not any((transaction/'incoming').iterdir()))
    for row in exposure['surfaces']:
        name=row['surface']
        require(publication.digest(transaction/'old'/name,name in publication.DIRECTORIES)==row['old_sha256'])
    require(not any((root/'consumption/quarantine').iterdir()))


def arm(sandbox):
    root=scoped(sandbox)
    with file_lock(root/'consumer.lock'):
        with publication.locked(root):
            transaction,plan,state=publication.load(root)
            require(state=='applied-awaiting-verification'
                and publication.positions(root,transaction,plan['surfaces'])==[2]*5)
            require(not any((transaction/'incoming').iterdir()))
            directory=root/'consumption';directory.mkdir(mode=0o700)
            (directory/'quarantine').mkdir(mode=0o700)
            publication.write_json(directory/'EXPOSURE.json',{'version':1,
                'scope':'isolated-cooperative-consumers','ready_for_live_apply':False,
                'publication_plan_sha256':document_sha(transaction/'PLAN.json'),
                'publication_status_sha256':document_sha(transaction/'STATUS.json'),
                'surfaces':plan['surfaces']})
            set_status(directory,'open');publication.sync(directory);publication.sync(root)
            checkpoint('opened')


@contextmanager
def writer(sandbox):
    root=scoped(sandbox)
    # Hold this SH lock throughout every write and all spawned writer lifetimes.
    # EX recovery refuses immediately while a cooperating writer still holds it.
    with file_lock(root/'consumer.lock',shared=True):
        with journal(root):
            transaction,directory,exposure,state=load(root)
            require(state=='open' and not (directory/'SEAL.json').exists()
                and not (directory/'SEAL.json').is_symlink())
            old_intact(root,transaction,exposure)
            require({p.name for p in (root/'current').iterdir()}==set(publication.SURFACES))
        yield root/'current'


def sealed_rows(directory,exposure):
    seal=publication.read_json(directory/'SEAL.json')
    require(isinstance(seal,dict) and set(seal)=={'version','exposure_sha256','surfaces'}
        and type(seal['version']) is int and seal['version']==1
        and seal['exposure_sha256']==document_sha(directory/'EXPOSURE.json'))
    require(isinstance(seal['surfaces'],list) and len(seal['surfaces'])==5)
    for original,row in zip(exposure['surfaces'],seal['surfaces']):
        require(isinstance(row,dict) and set(row)=={'surface','old_sha256','consumed_sha256'}
            and row['surface']==original['surface'] and row['old_sha256']==original['old_sha256']
            and isinstance(row['consumed_sha256'],str)
            and re.fullmatch('[a-f0-9]{64}',row['consumed_sha256']) is not None)
    return seal['surfaces']


def seal_locked(root,transaction,directory,exposure,state):
    require(state in {'open','sealing','sealed'})
    old_intact(root,transaction,exposure)
    require({p.name for p in (root/'current').iterdir()}==set(publication.SURFACES))
    if state=='sealed':require((directory/'SEAL.json').is_file() and not (directory/'SEAL.json').is_symlink())
    if state=='open':
        require(not (directory/'SEAL.json').exists() and not (directory/'SEAL.json').is_symlink())
        # Persist the fence before hashing. A crash cannot reopen writers while
        # a final seal exists but STATUS has not yet advanced to sealed.
        set_status(directory,'sealing');checkpoint('sealing')
    if (directory/'SEAL.json').exists() or (directory/'SEAL.json').is_symlink():
        rows=sealed_rows(directory,exposure)
    else:
        rows=[{'surface':row['surface'],'old_sha256':row['old_sha256'],
               'consumed_sha256':publication.digest(root/'current'/row['surface'],row['surface'] in publication.DIRECTORIES)}
              for row in exposure['surfaces']]
        # No cooperative writers hold the shared fence. Recheck all captured
        # hashes and old state before publishing the durable final seal.
        old_intact(root,transaction,exposure)
        for row in rows:
            require(publication.digest(root/'current'/row['surface'],row['surface'] in publication.DIRECTORIES)==row['consumed_sha256'])
        publication.write_json(directory/'SEAL.json',{'version':1,
            'exposure_sha256':document_sha(directory/'EXPOSURE.json'),'surfaces':rows})
        checkpoint('seal-written')
    for row in rows:
        require(publication.digest(root/'current'/row['surface'],row['surface'] in publication.DIRECTORIES)==row['consumed_sha256'])
    old_intact(root,transaction,exposure)
    set_status(directory,'sealed');checkpoint('sealed')
    return rows


def seal(sandbox):
    root=scoped(sandbox)
    with file_lock(root/'consumer.lock'),journal(root):
        transaction,directory,exposure,state=load(root)
        seal_locked(root,transaction,directory,exposure,state)


def positions(root,transaction,directory,rows):
    states=[]
    for row in rows:
        name=row['surface'];is_dir=name in publication.DIRECTORIES
        def value(path):
            return publication.digest(path,is_dir) if path.exists() or path.is_symlink() else None
        observed=(value(root/'current'/name),value(transaction/'old'/name),value(directory/'quarantine'/name))
        old,new=row['old_sha256'],row['consumed_sha256']
        choices=[(new,old,None),(None,old,new),(old,None,new)]
        require(observed in choices);states.append(choices.index(observed))
    return states


def recover(sandbox):
    root=scoped(sandbox)
    with file_lock(root/'consumer.lock'),journal(root):
        transaction,directory,exposure,state=load(root)
        if state in {'open','sealing','sealed'}:
            rows=seal_locked(root,transaction,directory,exposure,state)
        else:rows=sealed_rows(directory,exposure)
        require(not any((transaction/'incoming').iterdir()))
        states=positions(root,transaction,directory,rows)
        if state=='reverted':
            require(states==[2]*5);return
        # Validate all surfaces before the first move. Unknown/tampered state
        # is held for review; never guess from a single unit's position.
        set_status(directory,'rolling-back');checkpoint('rolling-back')
        for row,position in reversed(list(zip(rows,states))):
            name=row['surface']
            if position==0:
                publication.move(root/'current'/name,directory/'quarantine'/name)
                checkpoint('quarantine:'+name)
            if position in (0,1):
                publication.move(transaction/'old'/name,root/'current'/name)
                checkpoint('restore:'+name)
        require(positions(root,transaction,directory,rows)==[2]*5)
        set_status(directory,'reverted');checkpoint('reverted')
