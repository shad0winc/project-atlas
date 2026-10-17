"""Prepare the disposable native baseline from extracted, validated archive members."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
MEMBERS = {'database.dump': 'backend-recovery/dispatcharr/database.dump',
           'dispatcharr-jwt': 'backend-recovery/dispatcharr/jwt',
           'teamarr-db': 'backend-recovery/teamarr/teamarr.db'}
MAX_MEMBER = 512*1024**2


def require(value):
    if not value: raise ValueError('Isolated archive-to-native restoration held')


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for raw in iter(lambda: stream.read(1024*1024), b''): result.update(raw)
    return result.hexdigest()


def extract(native, archive, env, destination):
    archive, destination = Path(archive), Path(destination)
    native.workspace(destination.parent)
    require(destination.name == 'archive-extracted' and not destination.exists() and not destination.is_symlink())
    require(archive.parent == Path(env['ATLAS_BACKUP_DIR']))
    support = load('archive_restore_validation', 'scripts/lib/sports-backup-archive.py')
    require(support.validate(archive, env))
    before = sha(archive)
    destination.mkdir(mode=0o700)
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getmembers(); names = [member.name.rstrip('/') for member in members]
        require(len(names) == len(set(names)))
        by_name = {member.name.rstrip('/'): member for member in members}
        for name, member_name in MEMBERS.items():
            member = by_name[member_name]
            require(member.isfile() and 0 < member.size <= MAX_MEMBER and member.mode == 0o600)
            target = destination/name
            descriptor = os.open(target, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
            size = 0
            with os.fdopen(descriptor, 'wb') as out, source.extractfile(member) as stream:
                for raw in iter(lambda: stream.read(1024*1024), b''):
                    size += len(raw); require(size <= member.size); out.write(raw)
                require(size == member.size); out.flush(); os.fsync(out.fileno())
            require(sha(target) == sha(Path(env['NATIVE_PAYLOAD'])/member_name))
    native.pub.sync(destination)
    require(sha(archive) == before)
    receipt = {'version': 1, 'scope': 'synthetic-archive-native-members', 'archive_sha256': before,
               'members': {name: sha(destination/name) for name in MEMBERS},
               'production_state_access': False, 'live_restore_enabled': False}
    native.pub.write_json(destination/'EXTRACTED.json', receipt)
    return receipt


def promote(native, baseline, candidate):
    baseline, candidate = Path(baseline), Path(candidate)
    native.workspace(baseline.parent)
    require(baseline.name == 'baseline' and candidate == baseline.parent/'archive-candidate')
    pub = native.pub
    require({path.name for path in candidate.iterdir()} == set(native.NATIVE)|{'PROVENANCE.json'})
    proof = pub.read_json(candidate/'PROVENANCE.json')
    expected = {'version', 'scope', 'archive_sha256', 'dump_sha256', 'helper_receipt',
                'surfaces', 'production_state_access', 'live_restore_enabled'}
    require(set(proof) == expected and type(proof['version']) is int and proof['version'] == 1
            and proof['scope'] == 'synthetic-archive-prepared-native-baseline'
            and proof['production_state_access'] is False and proof['live_restore_enabled'] is False)
    for key in ('archive_sha256', 'dump_sha256'): require(re.fullmatch('[a-f0-9]{64}', proof[key]))
    strict = load('archive_promote_strict', 'scripts/lib/sports-strict-consumption.py')
    strict.validate_receipt(proof['helper_receipt'])
    require(proof['helper_receipt']['dump_sha256'] == proof['dump_sha256'])
    capture = pub.read_json(baseline/'CAPTURE.json')
    require(set(capture['surfaces']) == set(native.NATIVE) and set(proof['surfaces']) == set(native.NATIVE))
    for name in native.NATIVE:
        require(pub.digest(baseline/name, name == 'dispatcharr-db') == capture['surfaces'][name])
        require(pub.digest(candidate/name, name == 'dispatcharr-db') == proof['surfaces'][name])
    for name in ('PRE_ARCHIVE', 'PRE_ARCHIVE_CAPTURE.json', 'ARCHIVE_RESTORED.json'):
        require(not (baseline/name).exists() and not (baseline/name).is_symlink())
    # Baseline has not yet been exposed to consumers; incomplete promotion holds
    # this diagnostic. The prior native bytes and receipt remain available.
    previous = baseline/'PRE_ARCHIVE'; previous.mkdir(mode=0o700)
    for name in native.NATIVE:
        pub.move(baseline/name, previous/name)
        pub.move(candidate/name, baseline/name)
    pub.move(baseline/'CAPTURE.json', baseline/'PRE_ARCHIVE_CAPTURE.json')
    proof['previous_capture_sha256'] = native.consumer.document_sha(baseline/'PRE_ARCHIVE_CAPTURE.json')
    pub.write_json(baseline/'ARCHIVE_RESTORED.json', proof)
    capture['surfaces'] = proof['surfaces']
    capture['archive_restore_sha256'] = native.consumer.document_sha(baseline/'ARCHIVE_RESTORED.json')
    pub.write_json(baseline/'CAPTURE.json', capture)
    pub.sync(baseline)


def prepare_extracted(native, extracted, baseline, base, dispatch):
    extracted, baseline = Path(extracted), Path(baseline)
    work = native.workspace(baseline.parent); require(extracted == work/'archive-extracted')
    candidate = work/'archive-candidate'; require(not candidate.exists())
    candidate.mkdir(mode=0o700)
    source_id, target_id = uuid.uuid4().hex, uuid.uuid4().hex
    _, source = native.fence.names(source_id, 'dispatcharr')
    _, target = native.fence.names(target_id, 'dispatcharr')
    helper = 'atlas-archive-restore-prepare-'+source_id
    old_label = dispatch.LABEL
    archive_receipt = native.pub.read_json(extracted/'EXTRACTED.json')
    require(archive_receipt['production_state_access'] is False and archive_receipt['live_restore_enabled'] is False)
    for name in MEMBERS: require(sha(extracted/name) == archive_receipt['members'][name])
    cold_before = native.shape(baseline/'COLD_CLUSTER', True, (0, 0))
    try:
        for identifier, volume in ((source_id, source), (target_id, target)):
            base.docker('volume', 'create', '--driver', 'local', '--label', native.fence.LABEL+'='+identifier, volume)
            row = json.loads(base.docker('volume', 'inspect', volume))[0]
            require(row['Name'] == volume and row['Driver'] == 'local' and not row.get('Options')
                    and row.get('Labels', {}).get(native.fence.LABEL) == identifier)
            path = native.volume_path(identifier, 'dispatcharr')
            require(not any(path.iterdir())); path.chmod(0o700); os.chown(path, 1000, 1000)
        source_path = native.volume_path(source_id, 'dispatcharr')
        target_path = native.volume_path(target_id, 'dispatcharr')
        native.copy_tree(baseline/'COLD_CLUSTER', source_path/'db', True, (0, 0), (1000, 1000))
        native.copy_tree(extracted/'database.dump', source_path/'atlas-cold-copy.dump', False, (0, 0), (1000, 1000))
        source_before = native.shape(source_path, True, (1000, 1000))
        dispatch.LABEL = native.fence.LABEL
        data, bootstrap = dispatch.payload(ROOT)
        base.invoke(*dispatch.helper_arguments(base, helper, source, target, source_id, bootstrap, 'prepare'))
        item = dispatch.inspect_helper(base, helper, source, target, source_id, 'prepare')
        require(item['State']['Status'] == 'created' and not item['State']['Running'])
        require(native.fence.references(source) == {item['Id']} and native.fence.references(target) == {item['Id']})
        print('ARCHIVE_EXTRACTED_DUMP_PREPARATION=running', flush=True)
        result = base.invoke('docker', 'start', '--attach', '--interactive', helper, input=data, timeout=180, check=False)
        require(result.returncode == 0 and len(result.stdout) <= 4096)
        receipt = json.loads(result.stdout)
        strict = load('archive_restore_strict', 'scripts/lib/sports-strict-consumption.py')
        strict.validate_receipt(receipt)
        require(receipt['dump_sha256'] == archive_receipt['members']['database.dump'])
        stopped = dispatch.inspect_helper(base, helper, source, target, source_id, 'prepare')
        require(stopped['Id'] == item['Id']); dispatch.exited(stopped)
        base.docker('rm', item['Id'])
        require(not native.fence.references(source) and not native.fence.references(target))
        require(native.shape(source_path, True, (1000, 1000)) == source_before)
        native.copy_tree(target_path/'db', candidate/'dispatcharr-db', True, (1000, 1000))
        for name in ('dispatcharr-jwt', 'teamarr-db'):
            native.copy_tree(extracted/name, candidate/name, False, (0, 0))
        native.pub.write_json(candidate/'PROVENANCE.json', {
            'version': 1, 'scope': 'synthetic-archive-prepared-native-baseline',
            'archive_sha256': archive_receipt['archive_sha256'], 'dump_sha256': receipt['dump_sha256'],
            'helper_receipt': receipt,
            'surfaces': {name: native.pub.digest(candidate/name, name == 'dispatcharr-db') for name in native.NATIVE},
            'production_state_access': False, 'live_restore_enabled': False})
        require(native.shape(baseline/'COLD_CLUSTER', True, (0, 0)) == cold_before)
    finally:
        try: base.cleanup([helper], source, source_id)
        finally:
            try: base.cleanup([], target, target_id)
            finally: dispatch.LABEL = old_label
    return candidate


def prepare_baseline(native, sandbox, baseline, base, dispatch):
    archive_support = load('archive_restore_command', 'scripts/lib/sports-backup-archive.py')
    original_readback = archive_support.roundtrip
    completed = []
    def readback(native_module, archive, env):
        require(not completed and native_module is native)
        digest = original_readback(native, archive, env)
        extracted = Path(baseline).parent/'archive-extracted'
        require(extract(native, archive, env, extracted)['archive_sha256'] == digest)
        candidate = prepare_extracted(native, extracted, baseline, base, dispatch)
        completed.append(candidate)
        return digest
    # Scoped in-memory fixture extension; the pinned archive command/helper
    # sources are unchanged. Its original baseline immutability checks still run.
    archive_support.roundtrip = readback
    archive_support.prepare_baseline(native, sandbox, baseline, base, dispatch)
    require(len(completed) == 1)
    promote(native, baseline, completed[0])
    print('ARCHIVE_EXTRACTED_NATIVE_BASELINE_PROMOTED=PASS', flush=True)
