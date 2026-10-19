"""Private held acceptance bound to exact source, record, generation and runtime.

A private receipt is never a CI/public acceptance waiver or owner-release permit.
Only the host native coordinator writes gate logs; no web/socket API exists.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time

from atlas.deployment_held_publication import HeldPublication
from atlas.deployment_publication_journal import create_once, encoded, read_file, safe_directory, sync_directory
from atlas.maintenance_control import MaintenanceControlError


def digest(value):return hashlib.sha256(encoded(value)).hexdigest()


class PrivateHeldAcceptance(HeldPublication):
    maximum_age = 300

    def _command(self, *arguments):
        value = subprocess.run(arguments, capture_output=True, timeout=45,
            env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','PYTHONDONTWRITEBYTECODE':'1'})
        if value.returncode:raise MaintenanceControlError('acceptance_context_collection_failed')
        return value.stdout

    def _source(self, source):
        safe_directory(source)
        if source != Path(__file__).resolve().parents[1]:
            raise MaintenanceControlError('acceptance_source_root_differs')
        if self._command('git','-C',str(source),'branch','--show-current').strip() != b'main':
            raise MaintenanceControlError('acceptance_requires_clean_main')
        if self._command('git','-C',str(source),'status','--porcelain','--untracked-files=all').strip():
            raise MaintenanceControlError('acceptance_requires_clean_main')
        head = self._command('git','-C',str(source),'rev-parse','HEAD').decode().strip()
        tree = self._command('git','-C',str(source),'rev-parse','HEAD^{tree}').decode().strip()
        if re.fullmatch(r'[0-9a-f]{40}',head) is None or re.fullmatch(r'[0-9a-f]{40}',tree) is None:
            raise MaintenanceControlError('acceptance_source_identity_invalid')
        # The executing collector must match the tracked canonical collector.
        expected = self._command('git','-C',str(source),'show','HEAD:atlas/deployment_private_acceptance.py')
        if hashlib.sha256(expected).hexdigest() != read_file(Path(__file__)):
            raise MaintenanceControlError('acceptance_collector_source_differs')
        import importlib
        executing={}
        for name in ('atlas.maintenance_control','atlas.maintenance_transaction','atlas.deployment_publication_journal','atlas.deployment_held_publication'):
            loaded=importlib.import_module(name)
            raw=self._command('git','-C',str(source),'show','HEAD:'+name.replace('.','/')+'.py')
            actual=read_file(Path(loaded.__file__))
            if hashlib.sha256(raw).hexdigest()!=actual:
                raise MaintenanceControlError('acceptance_dependency_source_differs')
            executing[name]=actual
        return {'root':str(source),'commit':head,'tree':tree,'collector_sha256':hashlib.sha256(expected).hexdigest(),
                'executing_code_sha256':executing}

    def _runtime(self, record):
        expected = {}
        for line in read_file(record/'images.tsv',limit=1024*1024).decode('ascii').splitlines():
            fields = line.split('|')
            if (len(fields)!=7 or not all(fields) or re.fullmatch(r'/?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',fields[4]) is None
                    or re.fullmatch(r'sha256:[0-9a-f]{64}',fields[6]) is None or fields[4].lstrip('/') in expected):
                raise MaintenanceControlError('acceptance_image_inventory_invalid')
            expected[fields[4].lstrip('/')] = fields[6]
        if not expected:raise MaintenanceControlError('acceptance_image_inventory_empty')
        rows = json.loads(self._command('docker','inspect',*sorted(expected)))
        result = {};needed = ('Id','Image','Config','HostConfig','Mounts','State','RestartCount','Name')
        for row in rows:
            if not isinstance(row,dict) or any(key not in row for key in needed):
                raise MaintenanceControlError('acceptance_runtime_invalid')
            if not isinstance(row['Name'],str) or not isinstance(row['State'],dict):
                raise MaintenanceControlError('acceptance_runtime_invalid')
            name = row['Name'].lstrip('/');state = row['State']
            if (name in result or name not in expected or row['Image']!=expected[name]
                    or type(row['RestartCount']) is not int or row['RestartCount']<0
                    or type(state.get('Pid')) is not int or state['Pid']<=0
                    or re.fullmatch(r'[0-9a-f]{64}',row['Id']) is None
                    or state.get('Running') is not True or state.get('Paused') is not False
                    or state.get('Restarting') is not False or state.get('OOMKilled') is not False
                    or (state.get('Health') is not None and (not isinstance(state['Health'],dict) or state['Health'].get('Status')!='healthy'))):
                raise MaintenanceControlError('acceptance_runtime_unhealthy_or_changed')
            result[name] = {'id':row['Id'],'image':row['Image'],'restarts':row['RestartCount'],
                'state':{key:state.get(key) for key in ('Running','Paused','Restarting','OOMKilled','Pid','StartedAt')},
                'config_sha256':digest(row['Config']),'host_config_sha256':digest(row['HostConfig']),
                'mounts_sha256':digest(row['Mounts'])}
        if set(result)!=set(expected):raise MaintenanceControlError('acceptance_runtime_inventory_changed')
        return result

    def _generation_inventory(self, intent, source):
        self._generation(intent)
        root = self.root/'source/generations'/intent['publication_id'];result={};count=0
        for directory, directories, files in os.walk(root,followlinks=False):
            path=Path(directory);safe_directory(path)
            if len(path.relative_to(root).parts)>64:raise MaintenanceControlError('acceptance_generation_depth')
            for name in directories:
                child=path/name
                if child.is_symlink():raise MaintenanceControlError('acceptance_generation_link_invalid')
            for name in files:
                count+=1
                if count>20000:raise MaintenanceControlError('acceptance_generation_inventory_limit')
                child=path/name;relative=child.relative_to(root).as_posix()
                if child.is_symlink():
                    if relative!='.env' or os.readlink(child)!=str(source/'.env'):
                        raise MaintenanceControlError('acceptance_generation_link_invalid')
                    result[relative]={'link':str(source/'.env'),'target_sha256':read_file(source/'.env')}
                else:result[relative]={'sha256':read_file(child),'mode':child.stat().st_mode & 0o777}
        return digest(result)

    def _providers(self, source, path):
        # Use the exact canonical availability semantics; never import a historical fallback.
        import importlib.util
        spec=importlib.util.spec_from_file_location('atlas_acceptance_provider_health',source/'atlas/sports_provider_snapshot_health.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        # Provider state is legitimately written by the non-root controller.
        # Read one stable no-follow inode without requiring host-root ownership.
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>4*1024*1024:
                raise MaintenanceControlError('acceptance_provider_invalid')
            with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(4*1024*1024+1)
            after=os.fstat(fd)
            if len(raw)>4*1024*1024 or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
                raise MaintenanceControlError('acceptance_provider_changed')
        finally:os.close(fd)
        rows=json.loads(raw)
        if not isinstance(rows,dict) or not rows:raise MaintenanceControlError('acceptance_provider_missing')
        result=[]
        for name,row in rows.items():
            if not isinstance(row,dict) or row.get('status')!='healthy' or not module.provider_snapshot_usable(row):
                raise MaintenanceControlError('acceptance_provider_unhealthy')
            result.append({'provider_sha256':hashlib.sha256(str(name).encode()).hexdigest(),
                'status':row['status'],'refresh_state':row.get('refresh_state'),'last_success_at':row.get('last_success_at'),
                'bounded_snapshot_usable':True})
        return sorted(result,key=lambda row:row['provider_sha256'])

    def _snapshot(self, publication, source):
        intent=self._context(publication);pins,manifest=self._expected(intent)
        record=self.root/'deployments/records'/publication;self._record(record,pins,manifest)
        self._check_record_observation(publication,manifest)
        if self.state(publication)!='current-published':raise MaintenanceControlError('acceptance_requires_published_current')
        return {'source':self._source(source),'publication_id':publication,'original_owner':intent['original_owner'],
            'intent_sha256':read_file(self._paths(publication)[1]/'intent.json'),
            'record_manifest_sha256':hashlib.sha256(manifest).hexdigest(),
            'generation_sha256':self._generation_inventory(intent,source),'runtime':self._runtime(record),
            'current_sha256':read_file(self.root/'deployments/current')}

    def _boot(self):return hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()

    def _attempt(self, publication, attempt):
        if re.fullmatch(r'[0-9a-f]{32}',attempt) is None:raise MaintenanceControlError('acceptance_attempt_invalid')
        _,folder=self._paths(publication);path=folder/'private-attempts'/attempt
        safe_directory(path);return path

    def start(self, publication, source, provider_path):
        with self._exclusive():
            context=self._snapshot(publication,source);providers=self._providers(source,provider_path)
            _,folder=self._paths(publication);parent=folder/'private-attempts'
            try:parent.mkdir(mode=0o700);sync_directory(folder)
            except FileExistsError:safe_directory(parent)
            attempt=secrets.token_hex(16);path=parent/attempt;path.mkdir(mode=0o700);sync_directory(parent)
            create_once(path/'before.json',encoded({'schema_version':1,'publication_id':publication,
                'context':context,'providers_before':providers,'source_root':str(source),'provider_path':str(provider_path),
                'started_at':time.time(),'monotonic_started':time.monotonic(),'boot_sha256':self._boot()}))
            return path

    def finish(self, publication, attempt):
        with self._exclusive():
            path=self._attempt(publication,attempt)
            if (path/'receipt.json').exists():raise MaintenanceControlError('acceptance_receipt_already_exists')
            before=json.loads(read_file(path/'before.json',limit=4*1024*1024))
            now=time.time();elapsed=time.monotonic()-before['monotonic_started']
            if (before['schema_version']!=1 or before['publication_id']!=publication or before['boot_sha256']!=self._boot()
                    or not 0<=now-before['started_at']<=self.maximum_age or not 0<=elapsed<=self.maximum_age):
                raise MaintenanceControlError('acceptance_attempt_expired_or_rebooted')
            source=Path(before['source_root']);after=self._snapshot(publication,source)
            if before['context']!=after:raise MaintenanceControlError('acceptance_context_changed')
            providers=self._providers(source,Path(before['provider_path']))
            logs={}
            for stage in ('runtime','doctor','verify'):
                if read_file(path/(stage+'.exit'),limit=32)!=b'0\n':raise MaintenanceControlError('acceptance_gate_failed')
                raw=read_file(path/(stage+'.log'),limit=16*1024*1024);text=raw.decode(errors='replace')
                if stage=='doctor':
                    states=re.findall(r'^\s+(OK|WARN|FAIL|UNKNOWN)\s+.+?:',text,re.MULTILINE)
                    if not states or any(value!='OK' for value in states) or 'Overall Status: HEALTHY' not in text:
                        raise MaintenanceControlError('acceptance_doctor_not_healthy')
                elif stage=='verify' and ('Overall Status: PASS' not in text or re.search(r'^\s*FAIL(?:\s|$)',text,re.MULTILINE)):
                    raise MaintenanceControlError('acceptance_verify_not_passed')
                fd=os.open(path/(stage+'.log'),os.O_RDONLY|os.O_NOFOLLOW)
                try:os.fsync(fd)
                finally:os.close(fd)
                fd=os.open(path/(stage+'.exit'),os.O_RDONLY|os.O_NOFOLLOW)
                try:os.fsync(fd)
                finally:os.close(fd)
                logs[stage]={'exit_code':0,'log_sha256':hashlib.sha256(raw).hexdigest()}
            expected={'before.json'}|{stage+suffix for stage in logs for suffix in ('.exit','.log')}
            if {item.name for item in path.iterdir()}!=expected:raise MaintenanceControlError('acceptance_attempt_inventory_changed')
            if any(read_file(path/(stage+'.log'))!=row['log_sha256'] or read_file(path/(stage+'.exit'),limit=32)!=b'0\n'
                   for stage,row in logs.items()):raise MaintenanceControlError('acceptance_logs_changed')
            receipt={'schema_version':1,'scope':'fresh-private-held-acceptance','accepted_private':True,
                'public_acceptance_proven':False,'ci_acceptance_proven':False,'owner_release_permitted':False,
                'publication_id':publication,'attempt':attempt,'context':after,'stages':logs,
                'providers_before':before['providers_before'],'providers_after':providers,
                'started_at':before['started_at'],'finished_at':now,'elapsed_seconds':elapsed,
                'before_sha256':read_file(path/'before.json'),'original_owner_retained':True}
            create_once(path/'receipt.json',encoded(receipt))
            return path/'receipt.json'

    def validate(self, publication, attempt, expected_sha256):
        with self._exclusive():
            path=self._attempt(publication,attempt);raw=read_file(path/'receipt.json',limit=4*1024*1024)
            if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise MaintenanceControlError('acceptance_receipt_changed')
            receipt=json.loads(raw);before=json.loads(read_file(path/'before.json',limit=4*1024*1024))
            if (receipt.get('schema_version')!=1 or receipt.get('scope')!='fresh-private-held-acceptance'
                    or receipt.get('accepted_private') is not True or receipt.get('publication_id')!=publication
                    or receipt.get('attempt')!=attempt or receipt.get('original_owner_retained') is not True
                    or receipt.get('owner_release_permitted') is not False
                    or receipt.get('public_acceptance_proven') is not False or receipt.get('ci_acceptance_proven') is not False
                    or receipt.get('before_sha256')!=read_file(path/'before.json')):
                raise MaintenanceControlError('acceptance_receipt_invalid')
            age=time.time()-before['started_at'];elapsed=time.monotonic()-before['monotonic_started']
            if not 0<=age<=self.maximum_age or not 0<=elapsed<=self.maximum_age or before['boot_sha256']!=self._boot():
                raise MaintenanceControlError('acceptance_receipt_expired_or_rebooted')
            expected={'before.json','receipt.json'}|{stage+suffix for stage in ('runtime','doctor','verify') for suffix in ('.log','.exit')}
            if {item.name for item in path.iterdir()}!=expected:raise MaintenanceControlError('acceptance_attempt_inventory_changed')
            if receipt.get('started_at')!=before['started_at'] or not before['started_at']<=receipt.get('finished_at',0)<=time.time():
                raise MaintenanceControlError('acceptance_receipt_time_invalid')
            context=self._snapshot(publication,Path(before['source_root']))
            if context!=receipt['context'] or context!=before['context']:
                raise MaintenanceControlError('acceptance_context_changed')
            if set(receipt['stages'])!={'runtime','doctor','verify'}:raise MaintenanceControlError('acceptance_stages_invalid')
            for stage,row in receipt['stages'].items():
                if row['exit_code']!=0 or read_file(path/(stage+'.exit'),limit=32)!=b'0\n' or read_file(path/(stage+'.log'))!=row['log_sha256']:
                    raise MaintenanceControlError('acceptance_logs_changed')
            self._providers(Path(before['source_root']),Path(before['provider_path']))
            return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--owner',required=True)
    parser.add_argument('--publication',required=True);parser.add_argument('--fd',type=int,required=True)
    parser.add_argument('--source',type=Path);parser.add_argument('--provider-path',type=Path)
    parser.add_argument('--attempt');parser.add_argument('action',choices=('start','finish'))
    args=parser.parse_args();value=PrivateHeldAcceptance(args.runtime_root,args.owner,args.fd)
    try:
        if args.action=='start':
            if args.source is None or args.provider_path is None:raise MaintenanceControlError('acceptance_input_missing')
            path=value.start(args.publication,args.source,args.provider_path)
        else:path=value.finish(args.publication,args.attempt or '')
        print(path);return 0
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError,MaintenanceControlError):
        print('ERROR: private acceptance refused; preserve original owner, marker and attempt evidence.',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
