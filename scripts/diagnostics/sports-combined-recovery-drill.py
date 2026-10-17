"""Rehearse five-surface publication, disposable consumer restarts and journal undo."""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid

HEAD='d5f3a813868fde036f517e47c412b08490266a52'
LABEL='io.project-atlas.combined-recovery-drill'
PINS={
 'scripts/diagnostics/sports-dispatcharr-recovery-drill.py':'a4844aa7f64856fcdbef32645c1d9197c99fb5f8618382eb9b94072fc25283d7',
 'scripts/diagnostics/sports-teamarr-recovery-drill.py':'68b4920da2fe6a2bca558de15879d941a65e591d3979ac9ee59e3c5ccd925e9e',
}
SUPPORT_HASHES = {'scripts/lib/sports-combined-recovery-drill.py': '78c331077d190283245e8109dba4c43c8d1fa70d7de8398f7fe90447804c8ec7', 'scripts/lib/sports-postgres-prepare.py': '34f3a813fcc51690af056b520a2d2e826efad757af3d387319f3a7a341e6a2bc', 'scripts/lib/sports-recovery-bundle.py': '87ffc4b729d36b9410dd0929fbf4bbc2385e21fd924ca018c97e453aa90cd00d', 'scripts/lib/sports-recovery-association.py': '74c3a0c381c2f51137b27e4eab7b183f51671feb741123deb6579ede811464e7', 'scripts/lib/sports-recovery-publication.py': '2d81b3e4f80c2125e20ab930c17f95522483dcfacc32ac56483dba74ef4652a0', 'scripts/lib/metadata-recovery.py': 'c8d98f872e7a84aacfb71edb8ee97961d26b816e415930f23ebc33792df79457', 'scripts/lib/sports-metadata-policy.py': '3680284e07edd90b39364569f6244df7ac01de2c9f5a4d050aa5ce77bc7f9a38', 'scripts/lib/sports-teamarr-recovery-drill.py': 'dcda557e3bb34a832458a19bf1fea1e409568cabbd02dd9c2adbd4668772660d', 'modules/sports/src/providers/__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'modules/sports/src/providers/metadata_store.py': '7fd660add05beba1d908c50a9542d65d39b1815c5428ef88207a4a4d37710632', 'modules/sports/src/providers/metadata_identity.py': '0fc6340a33a0a0e4852d2ef7e2a82f2ef1daf8b2356d1de2d2ef00666e98dfb2', 'modules/sports/src/providers/metadata_refresh.py': '48d2cc2e1e1522f3360dd9f5648172dbddd8efe16c65255896a96113ca822136', 'modules/sports/src/providers/metadata_broker.py': 'e04d683e85b7cff3fb166350cc428ecf96232eb5307b1f410430d7641464f9bc', 'modules/sports/src/providers/espn_metadata.py': '725de8493a94f99aba88ecdb0899da4390fbba9dc173d6ee10880c7a5c9a3596', 'modules/sports/src/providers/espn_directory.py': '26e0a119a5b132ff31d028857809193715b8c0a15606ccb712b67c79f06bafae'}


def require(value):
    if not value: raise RuntimeError('Synthetic combined Sports drill contract failed')


def component(root,path):
    source=root/path; require(source.is_file() and not source.is_symlink())
    require(hashlib.sha256(source.read_bytes()).hexdigest()==PINS[path])
    spec=importlib.util.spec_from_file_location('combined_'+source.stem.replace('-','_'),source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # Reviewed checkpoint for this new combined diagnostic; original component
    # files and their standalone guards remain unchanged.
    module.HEAD=HEAD;module.LABEL=LABEL
    return module


def normalize_inspect(original):
    def inspect(name):
        result=original(name)
        result['Mounts']=sorted(result['Mounts'],key=lambda m:json.dumps(m,sort_keys=True))
        return result
    return inspect


def defer_cleanup(module,groups):
    original=module.utilities
    def utilities(root):
        base=original(root);base.LABEL=LABEL
        base.inspect=normalize_inspect(base.inspect)
        cleanup=base.cleanup
        def defer(names,volume,identifier):
            groups.append((cleanup,tuple(names),volume,identifier))
        base.cleanup=defer
        return base
    module.utilities=utilities


class Progress:
    def __init__(self,output):self.output=output;self.pending=''
    def write(self,raw):
        self.pending+=raw
        while '\n' in self.pending:
            line,self.pending=self.pending.split('\n',1)
            if line.startswith('SYNTHETIC_') and ('STARTUP=pending' in line or
                ('=PASS' in line and 'RECOVERY_DRILL=PASS' not in line)):
                self.output.write(line+'\n');self.output.flush()
        return len(raw)
    def flush(self):self.output.flush()


def pack(root):
    data={}
    for name,digest in SUPPORT_HASHES.items():
        path=root/name;require(path.is_file() and not path.is_symlink())
        raw=path.read_bytes();require(hashlib.sha256(raw).hexdigest()==digest)
        data[name]=raw.decode()
    require(0<len(data)<=20)
    bootstrap=("import hashlib,json,pathlib,runpy,sys,tempfile\nr=sys.stdin.buffer.read(1048577)\nassert len(r)<=1048576\np=json.loads(r)\nh="
        +repr(SUPPORT_HASHES)+"\nassert set(p)==set(h)\n"
        +"assert all(hashlib.sha256(p[k].encode()).hexdigest()==v for k,v in h.items())\n"
        +"with tempfile.TemporaryDirectory(prefix='atlas-combined-code.') as t:\n"
        +" root=pathlib.Path(t)\n for k,v in p.items():\n  q=root/k;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(v);q.chmod(0o600)\n"
        +" sys.argv=['fixture',*sys.argv[1:]]\n runpy.run_path(str(root/'scripts/lib/sports-combined-recovery-drill.py'),run_name='__main__')\n")
    return json.dumps(data).encode(),bootstrap


def mount_plan(mode,handles,journal_path):
    dsource,dold,team,journal,dispatch_out,team_out,metadata_out=handles
    if mode=='collect':return [(dsource,'/dispatch-source',False),(dold,'/dispatch-old',False),
                              (team,'/team-source',False),(journal,journal_path,True)]
    if mode in {'stage','rollback'}:return [(dsource,'/dispatch-source',False),(journal,journal_path,True)]
    if mode=='materialize':return [(journal,journal_path,False),(dispatch_out,'/dispatch-target',True),
                                  (team_out,'/team-target',True),(metadata_out,'/metadata-target',True)]
    if mode=='probe':return [(journal,journal_path,False),(metadata_out,'/metadata-target',False)]
    if mode=='verify-consumers':return [(journal,journal_path,False),(dispatch_out,'/dispatch-target',False),(team_out,'/team-target',False)]
    raise RuntimeError('Unknown combined fixture mode')


def helper_arguments(base,name,identifier,bootstrap,mode,handles,journal_path):
    root=mode in {'collect','materialize','verify-consumers'}
    args=['docker','create','-i',*base.container_options(name,identifier),'--read-only',
          '--user='+('0:0' if root else '1000:1000'),'--cap-drop=ALL',
          '--tmpfs','/tmp:rw,nosuid,nodev,size=512m,mode=1777']
    if root:args+=['--cap-add=CHOWN','--cap-add=DAC_OVERRIDE','--cap-add=FOWNER']
    for volume,destination,writable in mount_plan(mode,handles,journal_path):
        args+=['--mount','type=volume,source='+volume+',destination='+destination+','
               +('' if writable else 'readonly,')+'volume-nocopy']
    return [*args,'--env','ATLAS_COMBINED_DRILL=1','--entrypoint','python3',base.IMAGE,
            '-I','-B','-c',bootstrap,mode,journal_path]


def attest(base,name,identifier,mode,handles,journal_path):
    item=base.inspect(name);host=item['HostConfig'];config=item['Config']
    require(item['Image']==base.IMAGE and config.get('Labels',{}).get(LABEL)==identifier
        and config['User']==('0:0' if mode in {'collect','materialize','verify-consumers'} else '1000:1000')
        and config['Entrypoint']==['python3'] and host['ReadonlyRootfs'] is True
        and host['NetworkMode']=='none' and not host.get('Privileged') and not host.get('PortBindings'))
    expected=mount_plan(mode,handles,journal_path)
    actual=[m for m in item['Mounts'] if m['Type']!='tmpfs']
    require(len(actual)==len(expected) and all(m['Type']=='volume' for m in actual))
    require(sorted((m['Name'],m['Destination'],m['RW']) for m in actual)==sorted(expected))
    return item


def check_receipt(raw,mode):
    require(len(raw)<=4096)
    value=json.loads(raw)
    expected={'version':1,'scope':'synthetic-combined-sports','mode':mode,'checks_passed':True,
              'production_state_access':False,'live_restore_enabled':False}
    require(set(value)==set(expected) and all(type(value[k]) is type(v) and value[k]==v for k,v in expected.items()))


def cleanup_all(groups):
    failed=False
    # The caller places combined helpers first: even exited helper containers
    # hold input-volume references. Then keep each component's own
    # container-before-volume order; do not reverse its two volume groups.
    for cleanup,names,volume,identifier in groups:
        try:cleanup(names,volume,identifier)
        except Exception:failed=True
    require(not failed)


def run():
    root=Path(__file__).resolve().parents[2]
    dispatch=component(root,'scripts/diagnostics/sports-dispatcharr-recovery-drill.py')
    team=component(root,'scripts/diagnostics/sports-teamarr-recovery-drill.py')
    base=dispatch.utilities(root);base.LABEL=LABEL;base.inspect=normalize_inspect(base.inspect)
    require(base.invoke('git','-C',str(root),'rev-parse','HEAD').stdout.decode().strip()==HEAD)
    require(base.invoke('git','-C','/opt/project-atlas','rev-parse','HEAD').stdout.decode().strip()==HEAD)
    require(not base.invoke('git','-C','/opt/project-atlas','status','--porcelain=v1').stdout)
    pointer=Path('/mnt/storage/configs/atlas/deployments/current')
    require(pointer.is_file() and not pointer.is_symlink())
    deployment=pointer.read_bytes();require(deployment.decode().strip()==base.DEPLOYMENT)
    before=dispatch.observation(base)
    payload,bootstrap=pack(root)
    groups=[];defer_cleanup(dispatch,groups);defer_cleanup(team,groups)
    phase='component-fixtures';applied=False;reverted=False
    try:
        with contextlib.redirect_stdout(Progress(sys.stdout)):
            dispatch.run();team.run()
        require(len(groups)==3)
        dsource=groups[0][2];dold=groups[1][2];tsource=groups[2][2]
        require(dsource.startswith('atlas-dispatch-drill-source-') and dold.startswith('atlas-dispatch-drill-target-')
                and tsource.startswith('atlas-teamarr-drill-data-'))
        # Every retained component container must already have exited.
        for _,names,_,identifier in groups:
            for name in names:
                item=base.inspect(name)
                require(item['Config']['Labels'].get(LABEL)==identifier and not item['State']['Running']
                        and item['State']['Pid']==0 and item['State']['Status']=='exited')
        print('COMBINED_COMPONENT_FIXTURES=PASS',flush=True)
        identifier=uuid.uuid4().hex
        volumes=['atlas-combined-'+kind+'-'+identifier for kind in ('journal','dispatch','team','metadata')]
        journal_path='/tmp/project-atlas-sports-publication.'+identifier
        handles=(dsource,dold,tsource,*volumes)
        containers=[]
        for index,volume in enumerate(volumes):
            # Free combined helper references before removing retained inputs.
            groups.insert(index,(base.cleanup,containers if index==0 else (),volume,identifier))
            base.docker('volume','create','--driver','local','--label',LABEL+'='+identifier,volume)
        count=0
        def helper(mode):
            nonlocal count
            count+=1;name='atlas-combined-helper-'+mode+'-'+identifier+'-'+str(count)
            containers.append(name)
            base.invoke(*helper_arguments(base,name,identifier,bootstrap,mode,handles,journal_path))
            attest(base,name,identifier,mode,handles,journal_path)
            print('COMBINED_HELPER_MODE='+mode,flush=True)
            result=base.invoke('docker','start','--attach','--interactive',name,input=payload,timeout=240,check=False)
            if result.returncode:print('COMBINED_FIXTURE_HELPER=FAIL mode='+mode,file=sys.stderr)
            require(result.returncode==0);check_receipt(result.stdout,mode)
            dispatch.exited(attest(base,name,identifier,mode,handles,journal_path))
        phase='collect-synthetic-inputs';helper('collect')
        phase='associate-publish-five-surfaces';helper('stage');applied=True
        print('COMBINED_FIVE_SURFACE_PUBLICATION=PASS',flush=True)
        phase='consumer-ownership-copies';helper('materialize');helper('probe')
        da='atlas-combined-dispatch-'+identifier;ta='atlas-combined-team-'+identifier
        tb=team.utilities(root);tb.IMAGE=team.IMAGE
        for app,volume,args in ((da,volumes[1],base.app_arguments(da,volumes[1],identifier)),
            (ta,volumes[2],team.app_arguments(base,ta,volumes[2],identifier))):
            containers.append(app);base.invoke(*args)
            (base if app==da else tb).owned_container(app,identifier,volume,'/data' if app==da else '/app/data',False)
        phase='combined-consumer-start'
        base.docker('start',da);dispatch.wait_ready(base,da,volumes[1],identifier)
        require(base.docker('exec','--user','1000:1000',da,'python3','-B','-c',dispatch.marker_code('snapshot'))=='marker-valid')
        # Teamarr's ownership/entrypoint attestation uses its own pinned image.
        base.docker('start',ta);team.wait_ready(tb,ta,identifier,volumes[2])
        require(base.docker('exec',ta,'python3','-B','-c',team.marker_code('snapshot'))=='marker-valid')
        require(base.docker('exec','--user','1000:1000',da,'python3','-B','-c',dispatch.marker_code('persisted-after-restore',True))=='marker-valid')
        change="import sqlite3\nc=sqlite3.connect('/app/data/teamarr.db');c.execute(\"UPDATE atlas_teamarr_probe SET marker='after-dump'\");c.commit();c.close();print('updated')\n"
        require(base.docker('exec',ta,'python3','-B','-c',change)=='updated')
        dispatch.stop(base,da,volumes[1],identifier);team.stop(tb,ta,identifier,volumes[2])
        phase='combined-persistence-restart'
        base.docker('start',da);dispatch.wait_ready(base,da,volumes[1],identifier)
        base.docker('start',ta);team.wait_ready(tb,ta,identifier,volumes[2])
        require(base.docker('exec','--user','1000:1000',da,'python3','-B','-c',dispatch.marker_code('persisted-after-restore'))=='marker-valid')
        require(base.docker('exec',ta,'python3','-B','-c',team.marker_code('after-dump'))=='marker-valid')
        dispatch.stop(base,da,volumes[1],identifier);team.stop(tb,ta,identifier,volumes[2])
        helper('probe');helper('verify-consumers')
        print('COMBINED_CONSUMER_RESTART_AND_IDENTITIES=PASS',flush=True)
        phase='journal-rollback';helper('rollback');reverted=True
        print('COMBINED_FIVE_SURFACE_ROLLBACK=PASS',flush=True)
    except Exception:
        print('COMBINED_RECOVERY_DRILL=FAIL phase='+phase,file=sys.stderr);raise
    finally:
        try:
            if applied and not reverted:
                try:helper('rollback')
                except Exception:print('COMBINED_JOURNAL_RECOVERY=FAIL',file=sys.stderr)
        finally:
            try:cleanup_all(groups)
            finally:require(pointer.read_bytes()==deployment and dispatch.observation(base)==before)
    print(json.dumps({'version':1,'scope':'synthetic-combined-sports-recovery','five_surface_publication':True,
        'consumer_copies_restarted':True,'jwt_preserved':True,'metadata_alias_budget_policy_preserved':True,
        'journal_rollback_verified':True,'consumer_writes_to_journal':False,
        'production_state_access':False,'live_restore_enabled':False},sort_keys=True))
    print('SYNTHETIC_COMBINED_SPORTS_RECOVERY_DRILL=PASS')
    print('STATE=synthetic-combined-recovery-only-production-unchanged')


def main():
    try:run();return 0
    except Exception:
        print('SYNTHETIC_COMBINED_SPORTS_RECOVERY_DRILL=FAIL; no production restore requested.',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
