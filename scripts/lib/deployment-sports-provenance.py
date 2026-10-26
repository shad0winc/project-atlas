"""Schema-3 Sports successor record validation. No live publication/action API.

The schema-2 base remains independently valid and unchanged. Its recipes and
historical service ledger are retained as history; effective writer/backend
origins are explicit overrides. Live admission/publication integration is pending.
"""
from pathlib import Path
import copy, hashlib, json, re, tarfile

SUPPLEMENTS = ('sports-runtime-extension.json', 'sports-application-source.tar.gz',
              'sports-application-tracked.json', 'sports-release-gate.json', 'sports-image-validation.json')
MARKERS = {'runtime_provenance_schema': '3', 'requires_mixed_runtime_contract': '3',
           'ingress_source_mode': 'base-recipes-with-explicit-maintenance-and-sports-extensions'}
SOURCE_CLAIM = 'verified-base-recipes-plus-independent-maintenance-and-sports-images'
JOBS = ('Release Contracts', 'API', 'Portal', 'Core Python', 'Sports', 'release-gate')
PREFIX = 'modules/sports-backend/dispatcharr-live-image/'
MUTABLE_METADATA = {'deployment_id', 'type', 'scope', 'reason', 'target_commit', 'previous_baseline',
                    'sports_extension_commit', 'sports_extension_tree', 'base_publication',
                    'runtime_provenance_schema', 'requires_mixed_runtime_contract', 'ingress_source_mode', 'source_claim'}

def need(value, message):
    if not value: raise ValueError(message)
def oid(value): return isinstance(value,str) and re.fullmatch('[a-f0-9]{40}',value) is not None
def sha(value): return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None
def image(value): return isinstance(value,str) and re.fullmatch('sha256:[a-f0-9]{64}',value) is not None
def identifier(value): return isinstance(value,str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,159}',value) is not None

def image_rows(raw):
    rows={}
    for line in raw.decode().splitlines():
        fields=line.split('|')
        need(len(fields)==7 and all(fields) and fields[4] not in rows,'Invalid Sports image manifest')
        rows[fields[4]]=fields
    return rows

def small_source(record,name):
    with tarfile.open(record/'sports-application-source.tar.gz','r:gz') as archive:
        member=archive.getmember(name)
        need(member.isfile() and member.size<=2*1024**2,'Invalid Sports source input')
        with archive.extractfile(member) as stream:return stream.read()

def expected_backend(record,archived):
    manifest=json.loads(small_source(record,PREFIX+'manifest.json'))
    overlays=manifest['overlay_files']
    need(isinstance(overlays,dict) and overlays,'Backend overlay provenance missing')
    result={}
    for name,pin in overlays.items():
        need(re.fullmatch(r'apps/[A-Za-z0-9_./-]+\.py',name) and '..' not in Path(name).parts and sha(pin),
             'Invalid backend overlay provenance')
        source=PREFIX+'overlay/'+name
        need(source in archived and archived[source]['sha256']==pin,'Backend overlay archive differs')
        result['/app/'+name]=pin
    worker=manifest['worker_environment']
    need(sha(worker['installed_entrypoint_sha256']) and sha(worker['installer_sha256'])
         and worker['login_launch_sites']==3 and worker['secret_values_written_to_profile'] is False,
         'Backend worker environment provenance differs')
    need(archived[PREFIX+'install_worker_environment.py']['sha256']==worker['installer_sha256'],
         'Backend worker installer source differs')
    result['/app/docker/entrypoint.sh']=worker['installed_entrypoint_sha256']
    for name in ('manifest.json','Dockerfile'):result['/app/'+name]=archived[PREFIX+name]['sha256']
    need(isinstance(manifest['base_image'],str) and re.fullmatch(r'[a-z0-9./_-]+@sha256:[a-f0-9]{64}',manifest['base_image']),
         'Backend immutable base provenance missing')
    return result,manifest['base_image'].split('@',1)[1]

def check_record(m,record):
    record=Path(record);need(record.is_dir() and record.resolve(strict=True)==record,'Linked Sports record')
    entries=m.verify_manifest(record);need(set(SUPPLEMENTS)<=set(entries),'Sports extension supplements missing')
    values=m.metadata(record)
    need(all(values.get(k)==v for k,v in MARKERS.items()) and values.get('source_claim')==SOURCE_CLAIM,
         'Sports metadata markers differ')
    ext=json.loads(m.read(record/SUPPLEMENTS[0]))
    need(set(ext)=={'schema_version','base_publication','source_archive_commit','released_commit','source_tree','components'},
         'Sports extension fields differ')
    need(type(ext['schema_version']) is int and ext['schema_version']==1,'Unsupported Sports extension schema')
    for key in ('source_archive_commit','released_commit','source_tree'):need(oid(ext[key]),'Invalid Sports source identity')
    link=ext['base_publication']
    need(isinstance(link,dict) and set(link)=={'id','manifest_sha256'} and identifier(link['id']) and sha(link['manifest_sha256'])
         and link['id']!=record.name,'Invalid Sports base link')
    base=record.parent/link['id']
    need(base.resolve(strict=True)==base and m.metadata(base).get('runtime_provenance_schema')=='2',
         'Sports successor requires one sealed schema-2 base')
    need(m.digest(base/'MANIFEST.sha256')==link['manifest_sha256'],'Sports base manifest link differs')
    base_ledger,controller_files,activation=m.check_record(base)
    base_entries=m.verify_manifest(base)
    need(set(entries)==set(base_entries)|set(SUPPLEMENTS),'Unexpected Sports successor evidence inventory')
    for name,pin in base_entries.items():
        if name not in ('metadata','images.tsv'):need(entries[name]==pin,'Sports successor changed inherited evidence')
    original=m.metadata(base)
    need(set(values)-set(original)<=MUTABLE_METADATA and set(original)<=set(values), 'Sports metadata inventory changed')
    need(all(values[k]==v for k,v in original.items() if k not in MUTABLE_METADATA),'Sports successor changed unrelated source meaning')
    need(values.get('deployment_id')==record.name and values.get('base_publication')==link['id']
         and values.get('previous_baseline')==link['id'] and values.get('scope')=='sports'
         and values.get('sports_extension_commit')==ext['released_commit']
         and values.get('sports_extension_tree')==ext['source_tree'],'Sports successor metadata identity differs')
    archived=m.archive_files(record/'sports-application-source.tar.gz',ext['source_archive_commit'])
    tracked=json.loads(m.read(record/'sports-application-tracked.json'))
    need(set(tracked)=={'commit','tree','files'} and tracked['commit']==ext['source_archive_commit']
         and tracked['tree']==ext['source_tree'],'Sports tracked identity differs')
    rows={}
    for item in tracked['files']:
        need(set(item)=={'path','mode','oid'},'Invalid Sports tracked row')
        m.safe_name(item['path'])
        need(item['path'] not in rows and item['mode'] in ('100644','100755'),'Invalid Sports tracked mode or duplicate')
        rows[item['path']]=item
    need(set(rows)==set(archived),'Sports tracked archive coverage differs')
    for name,item in rows.items():
        need(item['oid']==archived[name]['oid'] and (item['mode']=='100755')==archived[name]['executable'],
             'Sports tracked archive blob differs')
    need(m.extension_module().tree_oid(archived)==ext['source_tree'],'Sports archive Git tree differs')
    gate=json.loads(m.read(record/'sports-release-gate.json'))
    need(set(gate)=={'schema_version','event','head_sha','source_tree','workflow_path','run_id','run_attempt','conclusion','jobs'},
         'Sports release evidence fields differ')
    need(gate['schema_version']==1 and gate['event']=='push' and gate['head_sha']==ext['released_commit']
         and gate['source_tree']==ext['source_tree'] and gate['workflow_path']=='.github/workflows/release-gate.yml'
         and type(gate['run_id']) is int and gate['run_id']>0 and type(gate['run_attempt']) is int and gate['run_attempt']>0
         and gate['conclusion']=='success' and gate['jobs']=={name:'success' for name in JOBS},'Sports release evidence differs')
    components=ext['components'];need(set(components)=={'backend','writer'},'Sports image roles differ')
    proof=json.loads(m.read(record/'sports-image-validation.json'))
    need(set(proof)=={'schema_version','components'} and proof['schema_version']==1 and set(proof['components'])==set(components),
         'Sports image validation inventory differs')
    expected_backend_files,backend_base=expected_backend(record,archived)
    expected_files={'writer':m.expected_copies(archived),'backend':expected_backend_files}
    effective=image_rows(m.read(record/'images.tsv'));old_images=image_rows(m.read(base/'images.tsv'))
    targets={'writer':'/atlas-sports-writer','backend':'/atlas-dispatcharr'}
    need(set(effective)==set(old_images)|set(targets.values()),'Sports effective image coverage differs')
    for name,row in old_images.items():
        if name not in targets.values():need(effective[name]==row,'Sports successor changed an unrelated image')
    for role,item in components.items():
        need(set(item)=={'image_id','base_image_id','build_commit','build_tree','verified_source_commit','installed_file_sha256','validation_receipt_sha256'},
             'Sports component evidence fields differ')
        need(image(item['image_id']) and image(item['base_image_id']) and oid(item['build_commit']) and oid(item['build_tree'])
             and item['verified_source_commit']==ext['released_commit'] and sha(item['validation_receipt_sha256']),
             'Sports component source/image identity differs')
        need(item['installed_file_sha256']==expected_files[role],'Sports installed-file provenance differs')
        if role=='backend':need(item['base_image_id']==backend_base,'Backend base image differs')
        validation=proof['components'][role]
        need(set(validation)=={'image_id','source_commit','source_tree','source_files','receipt_sha256'}
             and validation['image_id']==item['image_id'] and validation['source_commit']==item['build_commit']
             and validation['source_tree']==item['build_tree'] and validation['receipt_sha256']==item['validation_receipt_sha256'],
             'Sports build receipt identity differs')
        inputs=validation['source_files'];need(isinstance(inputs,dict) and inputs,'Sports build input proof missing')
        # An older writer build may be reused only when its pinned build inputs
        # are byte-identical in the independently verified source archive.
        allowed=('modules/sports/',) if role=='writer' else (PREFIX,)
        for name,pin in inputs.items():
            m.safe_name(name);need(name.startswith(allowed) and name in archived and archived[name]['sha256']==pin,
                                 'Sports reused build input differs from verified source')
        required={name for name in archived if (role=='backend' and name.startswith(PREFIX+'overlay/'))}
        if role=='backend':required|={PREFIX+n for n in ('Dockerfile','manifest.json','install_live_pilot.py','install_worker_environment.py','verify_base.py','verify_overlay.py')}
        else:
            required={'modules/sports/Dockerfile.private-api'}
            for name in archived:
                if name.startswith('modules/sports/src/') and name.endswith('.py'):
                    destination='/srv/sports/'+name[len('modules/sports/src/'):]
                    if destination in expected_files['writer']:required.add(name)
        need(required<=set(inputs),'Sports build input coverage incomplete')
        row=effective[targets[role]]
        need(row[6]==item['image_id'],'Sports effective image manifest differs')
        need(row[5]==item['image_id'],'Sports image reference must be immutable')
        if targets[role] in old_images:need(row[:5]==old_images[targets[role]][:5],'Sports writer recipe identity changed')
    # Return an explicitly effective ledger. The sealed service-sources.json is
    # inherited history and is never rewritten to pretend the controller moved.
    effective_ledger=copy.deepcopy(base_ledger)
    writer=effective_ledger['ingress']['overrides']['sports-writer'];writer.update(
        code_commit=ext['released_commit'],image=components['writer']['image_id'],source_archive='sports-application-source.tar.gz',
        copied_file_sha256=expected_files['writer'],image_build_commit=components['writer']['build_commit'])
    effective_ledger['sports']['backend']={'image':components['backend']['image_id'],'verified_source_commit':ext['released_commit'],
        'source_archive':'sports-application-source.tar.gz','image_build_commit':components['backend']['build_commit']}
    return effective_ledger,controller_files,activation

def successor_proof(m,record,previous_publication):
    """Native read-only callback for archived completion continuity inspection."""
    need(identifier(previous_publication),'Invalid historical publication')
    check_record(m,record)
    ext=json.loads(m.read(record/'sports-runtime-extension.json'))
    need(ext['base_publication']['id']==previous_publication,'Successor has another historical base')
    return dict(previous_publication=previous_publication,successor_publication=record.name,
        previous_manifest_sha256=ext['base_publication']['manifest_sha256'],
        successor_manifest_sha256=m.digest(record/'MANIFEST.sha256'))
