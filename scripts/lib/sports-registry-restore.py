"""Private sixteen-registry replacement acceptance; production format3 stays blocked."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SURFACES = (
 ('users','state/users','required','directory'),
 ('identity-invitations','state/identity/invitations','optional','directory'),
 ('favorites','state/identity/favorites','required','directory'),
 ('dislikes','state/identity/dislikes','required','directory'),
 ('requests','state/requests/requests.json','optional','file'),
 ('scheduler','state/scheduler/tasks.json','required','file'),
 ('runtime-events','state/runtime/events.jsonl','required','file'),
 ('runtime-subscribers','state/runtime/subscribers','required','directory'),
 ('retention','state/retention','required','directory'),
 ('sports-subscriptions','state/sports/subscriptions.json','required','file'),
 ('sports-live-tv-bindings','state/sports/live-tv-bindings.json','required','file'),
 ('sports-dispatcharr-channel-bindings','state/sports/dispatcharr-channel-bindings.json','required','file'),
 ('sports-live-sources','state/sports/live-sources.json','required','file'),
 ('sports-source-lifecycle','state/sports/source-lifecycle.json','required','file'),
 ('sports-recordings','state/sports/recordings.json','required','file'),
 ('sports-scheduler','state/sports/scheduler.json','required','file'),
)
FILES = {
 'state/users/users.json': {'schema_version':1,'users':{}},
 'state/identity/invitations/invitations.json': {'schema_version':1,'invitations':{}},
 'state/identity/favorites/favorites.json': {'schema_version':1,'favorites':{}},
 'state/identity/dislikes/dislikes.json': {'schema_version':1,'dislikes':{}},
 'state/requests/requests.json': {'schema_version':1,'requests':{}},
 'state/scheduler/tasks.json': {'schema_version':2,'tasks':{},'history':[]},
 'state/sports/subscriptions.json': {'subscriptions':[]},
 'state/sports/live-tv-bindings.json': {'version':1,'bindings':{}},
 'state/sports/dispatcharr-channel-bindings.json': {'version':1,'bindings':{}},
 'state/sports/live-sources.json': {'version':1,'sources':[]},
 'state/sports/source-lifecycle.json': {'version':1,'sources':[]},
 'state/sports/recordings.json': {}, 'state/sports/scheduler.json': {},
}
SHELL = r'''
set -euo pipefail
source "$RESTORE_COMMAND"
atlas_restore_load_recovery_library
atlas_execution_exclusion_acquire registry_fd || exit 1
: > "$CONTROL/maintenance"
printf '%s\n' registry-restore-rehearsal > "$CONTROL/owner"
atlas_backup_recovery_validate_staged_restore "$STAGE" || exit 1
atlas_backup_recovery_validate_apply_plan "$PLAN_FILE" "$TRANSACTION" || exit 1
# Prevalidate the entire exact private plan before displacing any row.
while IFS=$'\t' read -r surface action kind group staged destination; do
  atlas_backup_recovery_validate_restore_destination "$destination" "$kind" || exit 1
done < "$PLAN_FILE"
mkdir -m 700 "$TRANSACTION"
mkdir -m 700 "$TRANSACTION/live-rollback" "$TRANSACTION/incoming"
: > "$TRANSACTION/applied.tsv"
chmod 600 "$TRANSACTION/applied.tsv"
printf '%s\n' setup-held > "$TRANSACTION/status"
[[ "$FAIL_AFTER" != 0 ]] || exit 41
cp() {
  if [[ "$FAIL_COPY" == 1 && "$*" == *"$COPY_SURFACE"* ]]; then
    # A real prepared copy followed by failure exercises unpublished incoming
    # state without writing any path outside the private transaction.
    command cp "$@" || return 1
    return 1
  fi
  command cp "$@"
}
index=0
while IFS=$'\t' read -r surface action kind group staged destination; do
  index=$((index+1))
  old_present=false
  [[ ! -e "$destination" ]] || old_present=true
  if ! atlas_backup_recovery_apply_plan_row "$surface" "$action" "$kind" "$staged" "$destination" "$TRANSACTION"; then
    atlas_backup_recovery_revert_applied_state "$TRANSACTION" || exit 43
    exit 42
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$surface" "$kind" "$destination" "$TRANSACTION/live-rollback/$surface" "$old_present" >> "$TRANSACTION/applied.tsv"
  if [[ "$FAIL_AFTER" == "$index" ]]; then
    atlas_backup_recovery_revert_applied_state "$TRANSACTION" || exit 43
    exit 42
  fi
done < "$PLAN_FILE"
[[ "$index" == 16 ]] || exit 43
printf '%s\n' applied-awaiting-verification > "$TRANSACTION/status"
printf '%s\n' APPLIED
IFS= read -r -t 60 decision || exit 44
[[ "$decision" == accept ]] || exit 44
atlas_backup_recovery_finalize_applied_state "$TRANSACTION" || exit 45
rm -- "$CONTROL/maintenance" "$CONTROL/owner"
atlas_execution_exclusion_release "$registry_fd" || exit 46
printf '%s\n' VERIFIED
'''


def require(value):
    if not value: raise ValueError('Isolated sixteen-registry restore held')


def load(name, relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def scoped(root):
    root=Path(root)
    require(root.parent==Path('/tmp') and root.name.startswith('atlas-registry-restore.')
        and root.is_dir() and not root.is_symlink() and root.stat().st_uid==os.geteuid()
        and stat.S_IMODE(root.stat().st_mode)==0o700)
    return root


def environment(root):
    root=scoped(root); config=root/'configs'; runtime=config/'atlas'
    return {'PATH':os.environ['PATH'],'PYTHONDONTWRITEBYTECODE':'1','ATLAS_PROJECT_DIR':str(ROOT),
        'ATLAS_CONFIG_ROOT':str(config),'ATLAS_RUNTIME_CONFIG_DIR':str(runtime),
        'ATLAS_USERS_DIR':str(runtime/'users'),'ATLAS_IDENTITY_DIR':str(runtime/'identity'),
        'ATLAS_REQUESTS_DIR':str(runtime/'requests'),'ATLAS_SCHEDULER_STATE_FILE':str(runtime/'scheduler/tasks.json'),
        'ATLAS_ARI_DIR':str(runtime/'ari'),'SPORTS_CONFIG_DIR':str(config/'sportyfin'),
        'RECOVERY_LIBRARY':str(ROOT/'scripts/lib/backup-recovery.sh'),
        'RESTORE_COMMAND':str(ROOT/'scripts/commands/restore.sh')}


def shell(script, env, timeout=60):
    result=subprocess.run(['bash','-c','set -euo pipefail\n'+script],env=env,capture_output=True,timeout=timeout)
    require(len(result.stdout)<1_000_000 and len(result.stderr)<1_000_000)
    return result


def registry(env):
    result=shell('source "$RECOVERY_LIBRARY"; atlas_backup_recovery_surface_rows',env)
    require(result.returncode==0)
    rows=[line.split('\t') for line in result.stdout.decode().splitlines()]
    require(len(rows)==16 and len({row[0] for row in rows})==16)
    for row, expected in zip(rows,SURFACES):
        require(len(row)==6 and (row[0],row[2],row[3],row[4])==expected
            and Path(row[1]).is_relative_to(Path(env['ATLAS_CONFIG_ROOT']))
            and all(not parent.is_symlink() for parent in [Path(row[1]),*Path(row[1]).parents]))
    return rows


def populate(paths, *, optional=True, old=False):
    """Empty real schemas plus one valid event/subscriber, never placeholder JSON."""
    for surface, relative, requirement, kind in SURFACES:
        if requirement=='optional' and not optional: continue
        target=paths[relative]
        if kind=='directory': target.mkdir(parents=True,exist_ok=True,mode=0o700)
        else: target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    for relative, value in FILES.items():
        surface=next(row for row in SURFACES if relative==row[1] or relative.startswith(row[1]+'/'))
        if surface[2]=='optional' and not optional: continue
        target=paths[surface[1]]/Path(relative).relative_to(surface[1]) if surface[3]=='directory' else paths[relative]
        target.write_text(json.dumps(value,indent=2 if old else None)+'\n');target.chmod(0o600)
    event={'schema':2,'id':'evt-registry-fixture','timestamp':'2026-10-17T12:00:00Z',
        'event':'request.available','source':'private-registry-restore','payload':{'synthetic':True}}
    paths['state/runtime/events.jsonl'].write_text(json.dumps(event)+'\n')
    subscribers=paths['state/runtime/subscribers']
    (subscribers/'module-notifications.cursor').write_text('0\n')
    (subscribers/'module-notifications.filter').write_text('*\n')
    for path in paths.values():
        if path.exists():
            for child in [path,*path.rglob('*')] if path.is_dir() else [path]:
                child.chmod(0o700 if child.is_dir() else 0o600)


def consumer(stage):
    result=subprocess.run(['python3','-B',str(ROOT/'scripts/lib/validate-recovery-state.py'),str(stage),str(ROOT)],
        env={'PATH':os.environ['PATH'],'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,timeout=30)
    require(result.returncode==0 and len(result.stdout)<16384 and len(result.stderr)<16384)
    rows=[line.split()[:2] for line in result.stdout.decode().splitlines()]
    expected={row[0] for row in SURFACES}-{'runtime-events','runtime-subscribers'}|{'runtime'}
    require(len(rows)==15 and {row[1] for row in rows}==expected
        and all(row[0]=='PASS' or row[0]=='SKIP' and row[1] in {'identity-invitations','requests'} for row in rows))
    return rows


def manifest(stage, optional=True):
    lines=['surface\tarchive_path\trequirement\tpolicy','project-configuration\t.\trequired\tconfiguration-only']
    lines.extend('\t'.join((s,p,r,'captured' if optional or r!='optional' else 'absent-optional')) for s,p,r,k in SURFACES)
    (stage/'RECOVERY_MANIFEST.tsv').write_text('\n'.join(lines)+'\n');(stage/'RECOVERY_MANIFEST.tsv').chmod(0o600)


def private_archive_environment(env):
    root=Path(env['PRIVATE_ROOT'])
    require(root.parent==Path('/tmp') and root.name.startswith('atlas-backup-archive.')
        and root.is_dir() and not root.is_symlink() and root.stat().st_uid==os.geteuid()
        and stat.S_IMODE(root.stat().st_mode)==0o700
        and Path(env['ATLAS_CONFIG_ROOT'])==root/'configs'
        and Path(env['ATLAS_PROJECT_DIR'])==root/'project')
    require(all(not p.is_symlink() for p in [root,*root.parents])
        and not (root/'configs').is_symlink() and not (root/'project').is_symlink())
    return root


def populate_archive(env):
    private_archive_environment(env)
    rows=registry(env)
    for _,source,_,requirement,kind,_ in rows:
        path=Path(source)
        if path.exists():
            if path.is_dir():shutil.rmtree(path)
            else:path.unlink()
    populate({row[2]:Path(row[1]) for row in rows})


def setup_archive(module, native, root, files, **kwargs):
    env=module.original_setup(native,root,files,**kwargs)
    populate_archive(env)
    return env


def plan(root, stage, env):
    root=scoped(root); stage=Path(stage)
    require(stage.is_relative_to(root) and stage.is_dir() and not stage.is_symlink())
    with (stage/'RECOVERY_MANIFEST.tsv').open() as stream:
        policies=list(csv.DictReader(stream,delimiter='\t'))
    require(len(policies)==17 and {r['surface'] for r in policies}=={'project-configuration'}|{r[0] for r in SURFACES})
    by_surface={row['surface']:row for row in policies}; lines=[]
    for surface,destination,relative,requirement,kind,group in registry(env):
        row=by_surface[surface]
        require(row['archive_path']==relative and row['requirement']==requirement)
        source=stage/relative
        if row['policy']=='captured':
            require(source.exists() and not source.is_symlink() and source.is_dir()==(kind=='directory'))
            action='replace'; staged=str(source)
        else:
            require(row['policy']=='absent-optional' and requirement=='optional' and not source.exists())
            action='remove-if-present';staged='-'
        lines.append('\t'.join((surface,action,kind,group,staged,destination)))
    return '\n'.join(lines)+'\n'


def verification(native,root,stage,env):
    view=root/'consumer-view';require(not view.exists());view.mkdir(mode=0o700)
    native.copy_tree(stage/'RECOVERY_MANIFEST.tsv',view/'RECOVERY_MANIFEST.tsv',target_owner=(os.geteuid(),os.getegid()))
    for _,destination,relative,_,kind,_ in registry(env):
        source=Path(destination); target=view/relative
        if source.exists():
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            native.copy_tree(source,target,kind=='directory',target_owner=(os.geteuid(),os.getegid()))
    return consumer(view)


def trial(native,stage_source,fail_after=-1,fail_copy=False,reject_validation=False):
    require(type(fail_after) is int and -1<=fail_after<=16 and type(fail_copy) is bool and type(reject_validation) is bool
        and not (reject_validation and (fail_copy or fail_after>=0)))
    stage_source=Path(stage_source)
    require(stage_source==stage_source.resolve() and stage_source.is_relative_to('/tmp') and stage_source.is_dir() and not stage_source.is_symlink()
        and stage_source.stat().st_uid==os.geteuid() and stat.S_IMODE(stage_source.stat().st_mode)==0o700)
    with tempfile.TemporaryDirectory(prefix='atlas-registry-restore.',dir='/tmp') as temporary:
        root=Path(temporary);root.chmod(0o700);env=environment(root)
        stage=root/'stage';native.copy_tree(stage_source,stage,True,target_owner=(os.geteuid(),os.getegid()))
        # Keep the staged archive version intact. In particular, format3 is not
        # downgraded to get past the production restore-plan rejection.
        before_source=native.shape(stage,True)
        consumers=consumer(stage)
        rows=registry(env);paths={row[2]:Path(row[1]) for row in rows};populate(paths,old=True)
        before={relative:native.shape(path,kind=='directory') for _,_,relative,_,kind,_ in rows for path in [paths[relative]]}
        control=root/'control';control.mkdir(mode=0o700)
        transaction=Path(env['ATLAS_CONFIG_ROOT'])/'registry-transaction'
        plan_file=root/'plan.tsv';plan_file.write_text(plan(root,stage,env));plan_file.chmod(0o600)
        env.update(CONTROL=str(control),STAGE=str(stage),PLAN_FILE=str(plan_file),TRANSACTION=str(transaction),
            FAIL_AFTER=str(fail_after),FAIL_COPY='1' if fail_copy else '0',COPY_SURFACE='sports-live-sources',
            ATLAS_RUNTIME_CONFIG_DIR=str(control))
        process=subprocess.Popen(['bash','-c',SHELL],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,start_new_session=True)
        try:
            if fail_after>=0 or fail_copy:
                require(process.wait(timeout=40) in (41,42))
                require((control/'maintenance').is_file() and (control/'owner').read_text()=='registry-restore-rehearsal\n')
                for _,_,relative,_,kind,_ in rows:require(native.shape(paths[relative],kind=='directory')==before[relative])
                require((transaction/'status').read_text().strip()==('setup-held' if fail_after==0 else 'reverted'))
            else:
                import select
                require(select.select([process.stdout],[],[],40)[0] and process.stdout.readline(65)==b'APPLIED\n')
                require((control/'maintenance').is_file() and (transaction/'status').read_text().strip()=='applied-awaiting-verification')
                for _,_,relative,_,kind,_ in rows:
                    src=stage/relative;dest=paths[relative]
                    if src.exists():require(native.shape(src,kind=='directory')==native.shape(dest,kind=='directory'))
                    else:require(not dest.exists())
                require(verification(native,root,stage,environment(root))==consumers)
                if reject_validation:
                    # Corrupt only the readback view to prove a real consumer
                    # refusal blocks finalization without changing applied data.
                    (root/'consumer-view/state/users/users.json').write_text('{"schema_version":1,"users":[]}\n')
                    try:consumer(root/'consumer-view')
                    except ValueError:pass
                    else:raise ValueError('Expected consumer refusal was absent')
                    process.stdin.write(b'reject\n');process.stdin.flush()
                    require(process.wait(timeout=10)==44 and (control/'maintenance').is_file()
                        and (control/'owner').is_file()
                        and (transaction/'status').read_text().strip()=='applied-awaiting-verification'
                        and (transaction/'live-rollback').is_dir())
                    require(native.shape(stage,True)==before_source)
                    return {'surfaces':16,'failed_after':-1,'partial_copy':False,'held':True,'validation_rejected':True}
                process.stdin.write(b'accept\n');process.stdin.flush()
                require(select.select([process.stdout],[],[],10)[0] and process.stdout.readline(65)==b'VERIFIED\n')
                require(process.wait(timeout=10)==0 and not (control/'maintenance').exists() and not (control/'owner').exists())
                require((transaction/'status').read_text().strip()=='verified' and not (transaction/'live-rollback').exists())
            require(native.shape(stage,True)==before_source)
        finally:
            if process.poll() is None:
                import signal
                os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
            process.stdin.close();process.stdout.close()
    return {'surfaces':16,'failed_after':fail_after,'partial_copy':fail_copy,'held':fail_after>=0 or fail_copy}


def accept_archive(native,archive,env):
    archive_support=load('registry_archive_validation','scripts/lib/sports-backup-archive.py')
    source_root=private_archive_environment(env);archive=Path(archive)
    require(archive.parent==source_root/'backups' and not archive.parent.is_symlink() and archive.is_file() and not archive.is_symlink()
        and archive.stat().st_uid==os.geteuid() and stat.S_IMODE(archive.stat().st_mode)==0o600
        and archive_support.validate(archive,env))
    before=archive_support.sha(archive)
    with tempfile.TemporaryDirectory(prefix='atlas-registry-restore.',dir='/tmp') as temporary:
        root=Path(temporary);root.chmod(0o700)
        stage_env=environment(root);stage_env['ARCHIVE']=str(archive);stage_env['STAGE_PARENT']=str(root)
        result=shell('source "$RECOVERY_LIBRARY"; atlas_backup_recovery_stage_archive "$ARCHIVE" "$STAGE_PARENT"',stage_env,180)
        require(result.returncode==0)
        stage=Path(result.stdout.decode().strip());require(stage.parent==root and stage.name.startswith('project-atlas-restore.'))
        require((stage/'RECOVERY_FORMAT').read_text().strip()=='3')
        rows=consumer(stage);require(all(row[0]=='PASS' for row in rows))
        # The generic live plan must still refuse format3 after staging/validation.
        refusal=shell('source "$RECOVERY_LIBRARY"; atlas_backup_recovery_restore_plan "$STAGE"',dict(stage_env,STAGE=str(stage)))
        require(refusal.returncode!=0)
        for failure in range(17):
            trial(native,stage,fail_after=failure)
            print('SIXTEEN_REGISTRY_REVERT_HELD=PASS boundary='+str(failure),flush=True)
        trial(native,stage,fail_copy=True)
        trial(native,stage,reject_validation=True)
        trial(native,stage)
    require(archive_support.sha(archive)==before)
    print('SIXTEEN_REGISTRY_REPLACEMENT_CONSUMER_VALIDATION_AND_FINALIZE=PASS',flush=True)
    print(json.dumps({'version':1,'scope':'private-sixteen-registry-row-engine-acceptance',
        'archive_sha256':before,'registry_surfaces':16,'consumer_groups':15,'all_optional_captured':True,
        'held_boundaries':17,'partial_copy_reverted':True,'consumer_refusal_held':True,'production_format3_plan_blocked':True,
        'power_loss_recovery_proven':False,'full_production_operational_restore':False,
        'production_state_access':False,'live_restore_enabled':False},sort_keys=True),flush=True)


refresh=load('registry_refresh_parent','scripts/lib/sports-archive-refresh.py')


class Rehearsal(refresh.Rehearsal):
    def __init__(self):
        super().__init__()
        self.registry_archive_sha=None

    def prepare_baseline(self,native,sandbox,baseline,base,dispatch):
        metadata=refresh.writer.archive
        original_load=metadata.load
        def metadata_load(name,relative):
            module=original_load(name,relative)
            if name=='archive_metadata_native_restore':
                restore_load=module.load
                def scoped_load(key,path):
                    support=restore_load(key,path)
                    if key=='archive_restore_command':
                        support.original_setup=support.setup
                        support.setup=lambda *args,**kwargs:setup_archive(support,*args,**kwargs)
                        original_roundtrip=support.roundtrip
                        def roundtrip(n,archive,env):
                            digest=original_roundtrip(n,archive,env)
                            require(self.registry_archive_sha is None)
                            accept_archive(n,archive,env)
                            self.registry_archive_sha=digest
                            return digest
                        support.roundtrip=roundtrip
                    return support
                module.load=scoped_load
            return module
        metadata.load=metadata_load
        try:
            result=super().prepare_baseline(native,sandbox,baseline,base,dispatch)
            require(self.registry_archive_sha is not None and self.registry_archive_sha==self.archive_sha)
            print('SAME_ARCHIVE_SIXTEEN_REGISTRY_NATIVE_METADATA_BINDING=PASS',flush=True)
            return result
        finally:metadata.load=original_load
