"""Bind a checksum-sealed native verifier and offline record to the authority probe.

Loading validates code and evidence; it never installs a unit or starts a service.
The authority verifier's command boundary permits only two exact local systemd
show queries. Existing ordinary-update/schema-2 restore refusals are unchanged.
"""
from __future__ import annotations
import hashlib,json,os,re,stat,subprocess,types
from pathlib import Path
from atlas.deployment_authority_service import NativeAuthorityProbe
from atlas.deployment_component_rollout import require

FILES=('deployment-mixed-runtime.py','deployment-ingress-provenance.py')
PROPERTIES=('LoadState','ActiveState','SubState','FragmentPath','DropInPaths','NeedDaemonReload',
 'MainPID','NRestarts','ExecMainStartTimestampMonotonic','WorkingDirectory','User','Group')
UNIT='atlas-maintenance-control.service'
QUERIES=(('systemctl','show',UNIT,*('--property='+key for key in PROPERTIES)),
 ('systemctl','show',UNIT,'--property=UnitFileState','--value'))

def read_sealed(path,*,limit=128*1024*1024):
    path=Path(path)
    require(path.is_absolute() and path.resolve(strict=True)==path,'authority_binding_path_linked')
    for parent in (path.parent,*path.parents):
        info=parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and not info.st_mode&0o022
                or parent==Path('/tmp') and info.st_mode&stat.S_ISVTX
                or parent==Path('/var/tmp') and info.st_mode&stat.S_ISVTX,
                'authority_binding_parent_writable')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.geteuid()
                and not before.st_mode&0o022 and before.st_size<=limit,'authority_binding_file_unsafe')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(limit+1)
        after=os.fstat(fd)
        fields=lambda info:(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        require(len(raw)<=limit and fields(before)==fields(after),'authority_binding_file_changed')
        return raw
    finally:os.close(fd)

def local_query(args,*,data=None,timeout=30):
    require(tuple(args) in QUERIES and data is None and 0<timeout<=30,'authority_binding_query_scope_invalid')
    command=['/usr/bin/systemctl','--system','--no-ask-password','--no-pager',*args[1:]]
    try:
        result=subprocess.run(command,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C',
          'SYSTEMD_PAGER':'','SYSTEMD_COLORS':'0'},stdin=subprocess.DEVNULL,
          stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired):
        require(False,'authority_binding_query_uncertain')
    require(result.returncode==0,'authority_binding_query_failed')
    return result.stdout

class BoundAuthorityProbe:
    def __init__(self,source,source_pins,record,manifest_sha256):
        require(set(source_pins)==set(FILES) and all(re.fullmatch('[0-9a-f]{64}',v) for v in source_pins.values())
                and re.fullmatch('[0-9a-f]{64}',manifest_sha256),'authority_binding_pins_invalid')
        self.source,self.record=Path(source),Path(record)
        self.pins=dict(source_pins);self.manifest_sha256=manifest_sha256
        raw_files={name:read_sealed(self.source/name,limit=2*1024*1024) for name in FILES}
        require(all(hashlib.sha256(raw_files[name]).hexdigest()==self.pins[name] for name in FILES),
                'authority_binding_source_checksum_differs')
        modules={name:types.ModuleType('bound_'+name.replace('-','_').replace('.','_')) for name in FILES}
        # Execute the same verified bytes, rather than reopening a file through importlib.
        for name,module in modules.items():
            module.__file__=str(self.source/name)
            exec(compile(raw_files[name],module.__file__,'exec'),module.__dict__)
        self.reader=modules[FILES[0]];self.verifier=modules[FILES[1]]
        self.reader.extension_module=lambda:self.verifier
        self.verifier.query=local_query
        manifest=read_sealed(self.record/'MANIFEST.sha256',limit=1024*1024)
        require(hashlib.sha256(manifest).hexdigest()==manifest_sha256,'authority_binding_manifest_differs')
        self.record_pins={}
        for line in manifest.decode().splitlines():
            require(re.fullmatch('[0-9a-f]{64}  [A-Za-z0-9][A-Za-z0-9._-]*',line),
                    'authority_binding_manifest_invalid')
            sha,name=line.split('  ')
            require(name not in self.record_pins and name!='MANIFEST.sha256','authority_binding_manifest_duplicate')
            self.record_pins[name]=sha
        require({path.name for path in self.record.iterdir()}==set(self.record_pins)|{'MANIFEST.sha256'},
                'authority_binding_record_inventory_differs')
        self.check_binding()
        self.reader.check_record(self.record)
        require(self.reader.metadata(self.record).get('runtime_provenance_schema')=='2','authority_binding_schema2_required')
        self.extension=json.loads(read_sealed(self.record/'ingress-runtime-extension.json'))
        self.native=NativeAuthorityProbe(vars(self.verifier),self.reader,self.record,self.extension)
        self.target_fingerprint=self.native.target_fingerprint
        self.check_binding()
    def check_binding(self):
        for name,sha in self.pins.items():
            require(hashlib.sha256(read_sealed(self.source/name,limit=2*1024*1024)).hexdigest()==sha,
                    'authority_binding_source_checksum_differs')
        require(hashlib.sha256(read_sealed(self.record/'MANIFEST.sha256',limit=1024*1024)).hexdigest()==self.manifest_sha256,
                'authority_binding_manifest_differs')
        require({path.name for path in self.record.iterdir()}==set(self.record_pins)|{'MANIFEST.sha256'},
                'authority_binding_record_inventory_differs')
        for name,sha in self.record_pins.items():
            require(hashlib.sha256(read_sealed(self.record/name)).hexdigest()==sha,'authority_binding_record_checksum_differs')
        return True
    def preflight(self,*,require_unit=False):
        self.check_binding();result=self.native.preflight(require_unit=require_unit);self.check_binding();return result
    def observe(self):
        self.check_binding();result=self.native.observe();self.check_binding();return result
    def removed(self):
        self.check_binding();result=self.native.removed();self.check_binding();return result
