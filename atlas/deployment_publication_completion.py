"""Host-only publication-fence archival. Maintenance handoff remains explicit.

This mechanism grants no runtime, deployment or public acceptance. A trusted
host verifier must validate the native runtime at every transition. Completion
retains control-pending until a separately verified host maintenance handoff.
"""
from contextlib import contextmanager
import ctypes
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from atlas.maintenance_control import MaintenanceControlError


def require(value):
    if not value:
        raise MaintenanceControlError('publication_completion_refused')


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def directory(path):
    info=path.lstat()
    require(path.resolve(strict=True)==path and stat.S_ISDIR(info.st_mode)
            and info.st_uid==os.geteuid() and not info.st_mode & 0o022)
    return info


def read(path):
    directory(path.parent)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1
                and before.st_uid==os.geteuid() and not before.st_mode & 0o022
                and before.st_size<=131072)
        raw=os.read(fd,131073);after=os.fstat(fd)
        require(len(raw)==before.st_size and
                (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns))
        return raw,before
    finally:os.close(fd)


def identity(info,raw):
    return dict(device=info.st_dev,inode=info.st_ino,uid=info.st_uid,gid=info.st_gid,
                mode=stat.S_IMODE(info.st_mode),links=info.st_nlink,sha256=digest(raw))


def sync(path):
    info=directory(path);fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        require((os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(info.st_dev,info.st_ino))
        os.fsync(fd)
    finally:os.close(fd)


def note(path,raw):
    if os.path.lexists(path):
        require(read(path)[0]==raw)
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    else:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'wb',closefd=False) as stream:
                stream.write(raw);stream.flush();os.fsync(fd)
        finally:os.close(fd)
    sync(path.parent)


def rename_once(source,target):
    library=ctypes.CDLL(None,use_errno=True);rename=getattr(library,'renameat2',None)
    require(rename is not None)
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    left=os.open(source.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    right=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        require(os.fstat(left).st_dev==os.fstat(right).st_dev)
        if rename(left,os.fsencode(source.name),right,os.fsencode(target.name),1):
            raise MaintenanceControlError('publication_completion_rename_refused')
    finally:os.close(right);os.close(left)


class PublicationCompletion:
    def __init__(self,root,publication,inherited_fd,*,checkpoint=None):
        self.root=Path(root)
        require(self.root.is_absolute() and isinstance(publication,str)
                and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',publication)
                and type(inherited_fd) is int and inherited_fd>=3)
        self.publication=publication;self.fd=inherited_fd
        self.maintenance=self.root/'maintenance'
        self.parent=self.maintenance/'publication-completions'
        self.folder=self.parent/publication
        self.live=self.maintenance/'publication-pending'
        self.archived=self.folder/'publication-pending'
        self.pending=self.maintenance/'control-pending'
        self.checkpoint=checkpoint or (lambda phase:None)

    @contextmanager
    def exclusion(self):
        for path in (self.root,self.maintenance,self.root/'deployments'):directory(path)
        borrowed=os.dup(self.fd);probe=None
        try:
            info=os.fstat(borrowed);path=self.root/'deployment-scheduler.lock';on_disk=path.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid()
                    and not info.st_mode & 0o022 and path.resolve(strict=True)==path
                    and (info.st_dev,info.st_ino)==(on_disk.st_dev,on_disk.st_ino))
            probe=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            require((os.fstat(probe).st_dev,os.fstat(probe).st_ino)==(info.st_dev,info.st_ino))
            try:fcntl.flock(probe,fcntl.LOCK_SH|fcntl.LOCK_NB)
            except BlockingIOError:pass
            else:require(False)
            fcntl.flock(borrowed,fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield
        finally:
            if probe is not None:os.close(probe)
            os.close(borrowed)

    def context(self,plan):
        require(set(plan)=={'schema_version','publication_id','marker','maintenance_flag_sha256',
                            'archive_intent_sha256','archive_completed_sha256'})
        require(plan['schema_version']==1 and plan['publication_id']==self.publication)
        require(isinstance(plan['marker'],dict))
        flag,_=read(self.maintenance/'enabled')
        require(digest(flag)==plan['maintenance_flag_sha256'])
        require(read(self.root/'deployments/current')[0]==(self.publication+'\n').encode())
        require(not os.path.lexists(self.root/'deployments/update.lock'))
        journal=self.root/'deployments/publication-journals'/self.publication
        for name,key in (('owner-archive-intent.json','archive_intent_sha256'),
                         ('owner-archive-completed.json','archive_completed_sha256')):
            require(digest(read(journal/name)[0])==plan[key])
        locations=[path for path in (self.live,self.archived) if os.path.lexists(path)]
        require(len(locations)==1)
        raw,info=read(locations[0]);require(identity(info,raw)==plan['marker'])
        marker=json.loads(raw)
        require(marker.get('publication_id')==self.publication)
        require(digest(read(journal/'intent.json')[0])==marker.get('intent_sha256'))
        if os.path.lexists(self.folder):
            directory(self.folder)
            require({p.name for p in self.folder.iterdir()} <= {'intent.json','publication-pending','completed.json'})
        return 'marker-live' if locations[0]==self.live else 'marker-archived'

    def inspect(self,plan,admission):
        with self.exclusion():
            phase=self.context(plan)
            intent=encoded(dict(schema_version=1,scope='publication-fence-completion-only',plan=plan,admission=admission))
            durable=os.path.lexists(self.folder/'intent.json')
            if durable:require(read(self.folder/'intent.json')[0]==intent)
            fence=encoded(dict(schema_version=1,operation='publication-completion',publication_id=self.publication,
                               intent_sha256=digest(intent)))
            fenced=os.path.lexists(self.pending)
            if fenced:require(read(self.pending)[0]==fence)
            if phase=='marker-archived':require(durable and fenced)
            completed=os.path.lexists(self.folder/'completed.json')
            if completed:
                require(phase=='marker-archived' and fenced)
                require(read(self.folder/'completed.json')[0]==encoded(dict(schema_version=1,
                    intent_sha256=digest(intent),marker=plan['marker'],maintenance_handoff_pending=True)))
            return dict(phase='completed-maintenance-handoff-pending' if completed else
                        'marker-archived-needs-completion' if phase=='marker-archived' else
                        'intent-durable-marker-live' if durable else 'before-intent',
                        marker_path=str(self.live if phase=='marker-live' else self.archived),
                        maintenance_enabled=True,public_reopen_permitted=False,
                        maintenance_handoff_pending=fenced)

    def complete(self,plan,admission,*,admit):
        require(callable(admit) and isinstance(admission,dict) and admission
                and len(encoded(admission))<=65536)
        with self.exclusion():
            state=self.inspect(plan,admission)
            require(admit(plan,admission,state) is None)
            for path in (self.parent,self.folder):
                if not os.path.lexists(path):path.mkdir(mode=0o700);sync(path.parent)
                directory(path)
            intent=encoded(dict(schema_version=1,scope='publication-fence-completion-only',plan=plan,admission=admission))
            note(self.folder/'intent.json',intent);self.checkpoint('intent-durable')
            note(self.pending,encoded(dict(schema_version=1,operation='publication-completion',
                 publication_id=self.publication,intent_sha256=digest(intent))))
            self.checkpoint('control-fence-durable')
            state=self.inspect(plan,admission)
            require(admit(plan,admission,state) is None)
            if state['marker_path']==str(self.live):
                rename_once(self.live,self.archived);self.checkpoint('marker-renamed')
            sync(self.maintenance);sync(self.folder);self.checkpoint('marker-parents-durable')
            state=self.inspect(plan,admission)
            require(admit(plan,admission,state) is None)
            note(self.folder/'completed.json',encoded(dict(schema_version=1,intent_sha256=digest(intent),
                 marker=plan['marker'],maintenance_handoff_pending=True)))
            self.checkpoint('completion-durable')
            return self.inspect(plan,admission)
