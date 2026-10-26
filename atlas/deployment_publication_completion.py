"""Host-only publication completion and recoverable maintenance handoff.

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
        self.handoff_intent=self.folder/'handoff-intent.json'
        self.handoff_fence=self.folder/'control-pending'
        self.handoff_completed=self.folder/'handoff-completed.json'
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

    def context(self,plan,*,expected_current=None):
        require(set(plan)=={'schema_version','publication_id','marker','maintenance_flag_sha256',
                            'archive_intent_sha256','archive_completed_sha256'})
        require(plan['schema_version']==1 and plan['publication_id']==self.publication)
        require(isinstance(plan['marker'],dict))
        flag,_=read(self.maintenance/'enabled')
        require(digest(flag)==plan['maintenance_flag_sha256'])
        expected=self.publication if expected_current is None else expected_current
        require(isinstance(expected,str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',expected))
        require(read(self.root/'deployments/current')[0]==(expected+'\n').encode())
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
            require({p.name for p in self.folder.iterdir()} <= {'intent.json','publication-pending','completed.json',
                'handoff-intent.json','control-pending','handoff-completed.json'})
        return 'marker-live' if locations[0]==self.live else 'marker-archived'

    def inspect(self,plan,admission):
        return self._inspect(plan,admission)

    def _inspect(self,plan,admission,*,expected_current=None):
        with self.exclusion():
            phase=self.context(plan,expected_current=expected_current)
            intent=encoded(dict(schema_version=1,scope='publication-fence-completion-only',plan=plan,admission=admission))
            durable=os.path.lexists(self.folder/'intent.json')
            if durable:require(read(self.folder/'intent.json')[0]==intent)
            fence=encoded(dict(schema_version=1,operation='publication-completion',publication_id=self.publication,
                               intent_sha256=digest(intent)))
            fenced=os.path.lexists(self.pending)
            archived_fence=os.path.lexists(self.handoff_fence)
            require(not (fenced and archived_fence))
            if fenced:require(read(self.pending)[0]==fence)
            if archived_fence:require(read(self.handoff_fence)[0]==fence)
            completed=os.path.lexists(self.folder/'completed.json')
            if phase=='marker-archived':require(durable and (fenced or archived_fence))
            if completed:
                require(phase=='marker-archived')
                require(read(self.folder/'completed.json')[0]==encoded(dict(schema_version=1,
                    intent_sha256=digest(intent),marker=plan['marker'],maintenance_handoff_pending=True)))
            handoff_started=os.path.lexists(self.handoff_intent)
            handoff_done=os.path.lexists(self.handoff_completed)
            if archived_fence or handoff_started or handoff_done:
                require(completed and handoff_started and fenced!=archived_fence)
                raw,_=read(self.handoff_intent);handoff=json.loads(raw)
                require(set(handoff)=={'schema_version','scope','publication_id','completion_intent_sha256',
                    'completion_completed_sha256','control_fence','maintenance_flag','admission',
                    'maintenance_enabled','public_reopen_permitted'})
                require(handoff['schema_version']==1
                    and handoff['scope']=='publication-maintenance-handoff-only'
                    and handoff['publication_id']==self.publication
                    and handoff['completion_intent_sha256']==digest(intent)
                    and handoff['completion_completed_sha256']==digest(read(self.folder/'completed.json')[0])
                    and handoff['maintenance_enabled'] is True
                    and handoff['public_reopen_permitted'] is False
                    and isinstance(handoff['admission'],dict) and handoff['admission']
                    and len(encoded(handoff['admission']))<=65536
                    and raw==encoded(handoff))
                physical=self.pending if fenced else self.handoff_fence
                fence_raw,fence_info=read(physical)
                flag_raw,flag_info=read(self.maintenance/'enabled')
                require(identity(fence_info,fence_raw)==handoff['control_fence']
                    and identity(flag_info,flag_raw)==handoff['maintenance_flag'])
                if handoff_done:
                    require(archived_fence and read(self.handoff_completed)[0]==encoded(dict(
                        schema_version=1,handoff_intent_sha256=digest(raw),
                        control_fence=handoff['control_fence'],maintenance_flag=handoff['maintenance_flag'],
                        maintenance_enabled=True,public_reopen_permitted=False)))
            result_phase='completed-maintenance-held' if handoff_done else (
                'handoff-fence-archived-needs-completion' if archived_fence else
                'handoff-intent-durable-fence-live' if handoff_started else
                'completed-maintenance-handoff-pending' if completed else
                'marker-archived-needs-completion' if phase=='marker-archived' else
                'intent-durable-marker-live' if durable else 'before-intent')
            return dict(phase=result_phase,
                        marker_path=str(self.live if phase=='marker-live' else self.archived),
                        maintenance_enabled=True,public_reopen_permitted=False,
                        maintenance_handoff_pending=completed and not handoff_done or fenced)

    def inspect_completed_history(self,plan,admission,successor,*,verify_successor):
        """Read archived completion after an independently verified successor.

        This never authorizes completion, handoff, maintenance release or runtime
        actions. The normal inspect/complete/handoff APIs retain their old current
        pointer requirement. The verifier must use the native successor contract.
        """
        require(isinstance(successor,str) and successor!=self.publication
                and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',successor)
                and callable(verify_successor))
        with self.exclusion():
            before=read(self.root/'deployments/current')[0]
            require(before==(successor+'\n').encode())
            def verify():
                proof=verify_successor(self.publication,successor)
                require(isinstance(proof,dict) and set(proof)=={'previous_publication','successor_publication',
                    'previous_manifest_sha256','successor_manifest_sha256'})
                require(proof['previous_publication']==self.publication and proof['successor_publication']==successor)
                for publication,key in ((self.publication,'previous_manifest_sha256'),(successor,'successor_manifest_sha256')):
                    require(isinstance(proof[key],str) and re.fullmatch('[a-f0-9]{64}',proof[key]))
                    require(digest(read(self.root/'deployments/records'/publication/'MANIFEST.sha256')[0])==proof[key])
                return proof
            first=verify()
            result=self._inspect(plan,admission,expected_current=successor)
            require(result['phase']=='completed-maintenance-held' and not result['maintenance_handoff_pending'])
            require(verify()==first and read(self.root/'deployments/current')[0]==before)
            return dict(result,scope='archived-completion-continuity-only',historical_publication=self.publication,
                current_publication=successor,successor_proof_sha256=digest(encoded(first)),
                runtime_acceptance_granted=False,production_execution_authorized=False)

    def complete(self,plan,admission,*,admit):
        require(callable(admit) and isinstance(admission,dict) and admission
                and len(encoded(admission))<=65536)
        with self.exclusion():
            # Completion retries must never recreate a fence after handoff began.
            require(not any(os.path.lexists(path) for path in
                (self.handoff_intent,self.handoff_fence,self.handoff_completed)))
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

    def handoff(self,plan,admission,*,handoff_admission,admit):
        """Archive only this completion's fence; keep maintenance enabled.

        The host must establish fresh private/external/runtime admission through
        the callback. This method does not validate those proofs itself and never
        grants public reopening. Existing intent/admission bytes are immutable.
        """
        require(callable(admit) and isinstance(handoff_admission,dict)
            and handoff_admission and len(encoded(handoff_admission))<=65536)
        with self.exclusion():
            state=self.inspect(plan,admission)
            require(state['phase'] in ('completed-maintenance-handoff-pending',
                'handoff-intent-durable-fence-live','handoff-fence-archived-needs-completion',
                'completed-maintenance-held'))
            if os.path.lexists(self.handoff_intent):
                require(json.loads(read(self.handoff_intent)[0])['admission']==handoff_admission)
            require(admit(plan,admission,handoff_admission,state) is None)
            if not os.path.lexists(self.handoff_intent):
                fence,fence_info=read(self.pending)
                flag,flag_info=read(self.maintenance/'enabled')
                note(self.handoff_intent,encoded(dict(schema_version=1,
                    scope='publication-maintenance-handoff-only',publication_id=self.publication,
                    completion_intent_sha256=digest(read(self.folder/'intent.json')[0]),
                    completion_completed_sha256=digest(read(self.folder/'completed.json')[0]),
                    control_fence=identity(fence_info,fence),maintenance_flag=identity(flag_info,flag),
                    admission=handoff_admission,maintenance_enabled=True,public_reopen_permitted=False)))
            self.checkpoint('handoff-intent-durable')
            state=self.inspect(plan,admission)
            require(admit(plan,admission,handoff_admission,state) is None)
            if os.path.lexists(self.pending):
                rename_once(self.pending,self.handoff_fence)
                self.checkpoint('handoff-fence-renamed')
            sync(self.maintenance);sync(self.folder)
            self.checkpoint('handoff-parents-durable')
            state=self.inspect(plan,admission)
            require(admit(plan,admission,handoff_admission,state) is None)
            raw,_=read(self.handoff_intent);handoff=json.loads(raw)
            note(self.handoff_completed,encoded(dict(schema_version=1,
                handoff_intent_sha256=digest(raw),control_fence=handoff['control_fence'],
                maintenance_flag=handoff['maintenance_flag'],maintenance_enabled=True,
                public_reopen_permitted=False)))
            self.checkpoint('handoff-completion-durable')
            return self.inspect(plan,admission)
