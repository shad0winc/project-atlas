"""Strictly prepare a fixture dump, then promote only a private baseline copy."""
import hashlib
import json
import os
from pathlib import Path
import re
import uuid


def require(value):
    if not value: raise ValueError('Isolated strict consumption preparation held')


def validate_receipt(receipt):
    common = {'version': 1, 'scope': 'synthetic-dispatcharr-only', 'mode': 'prepare',
        'cold_source_unchanged': True, 'restored_cluster_stopped': True,
        'production_state_access': False, 'live_restore_enabled': False}
    require(isinstance(receipt, dict) and set(receipt) == set(common) | {'source_sha256', 'dump_sha256'})
    require(all(type(receipt[key]) is type(value) and receipt[key] == value for key, value in common.items()))
    for key in ('source_sha256', 'dump_sha256'):
        require(isinstance(receipt[key], str) and re.fullmatch('[a-f0-9]{64}', receipt[key]) is not None)


def promote(native, baseline, prepared, receipt):
    baseline, prepared = Path(baseline), Path(prepared)
    native.workspace(baseline.parent); require(baseline.name == 'baseline' and prepared == baseline/'strict-incoming')
    validate_receipt(receipt)
    pub = native.pub; capture = pub.read_json(baseline/'CAPTURE.json')
    require(set(capture) == {'version', 'marker', 'copied_wal', 'ledger_sha256', 'surfaces'}
        and type(capture['version']) is int and capture['version'] == 1
        and type(capture['copied_wal']) is bool and capture['marker'] == 'after-dump'
        and set(capture['surfaces']) == set(native.NATIVE))
    for name in native.NATIVE: require(pub.digest(baseline/name, name == 'dispatcharr-db') == capture['surfaces'][name])
    before = pub.digest(baseline/'dispatcharr-db', True); after = pub.digest(prepared, True)
    require(before != after)
    for name in ('COLD_CLUSTER', 'COLD_CAPTURE.json', 'STRICT_PREPARED.json'):
        require(not (baseline/name).exists() and not (baseline/name).is_symlink())
    # This baseline has not been exposed to consumers. An interruption here
    # holds the diagnostic; it never changes a journal or source native volume.
    pub.move(baseline/'dispatcharr-db', baseline/'COLD_CLUSTER')
    pub.move(prepared, baseline/'dispatcharr-db')
    pub.move(baseline/'CAPTURE.json', baseline/'COLD_CAPTURE.json')
    strict = {'version': 1, 'scope': 'synthetic-strict-dump-baseline',
        'raw_capture_sha256': native.consumer.document_sha(baseline/'COLD_CAPTURE.json'),
        'raw_cluster_sha256': before, 'prepared_cluster_sha256': after,
        'native_receipt': receipt, 'production_state_access': False, 'live_restore_enabled': False}
    pub.write_json(baseline/'STRICT_PREPARED.json', strict)
    capture['surfaces']['dispatcharr-db'] = after
    capture['strict_preparation_sha256'] = native.consumer.document_sha(baseline/'STRICT_PREPARED.json')
    pub.write_json(baseline/'CAPTURE.json', capture)
    require(all(pub.digest(baseline/name, name == 'dispatcharr-db') == capture['surfaces'][name] for name in native.NATIVE))
    pub.sync(baseline)


def prepare_baseline(native, sandbox, baseline, base, dispatch):
    root = native.consumer.scoped(sandbox); baseline = Path(baseline)
    native.workspace(baseline.parent)
    require(baseline.name == 'baseline' and base.IMAGE == native.fence.IMAGES['dispatcharr']
        and base.LABEL == native.fence.LABEL)
    identifier = uuid.uuid4().hex
    _, target = native.fence.names(identifier, 'dispatcharr')
    helper = 'atlas-strict-consumption-prepare-' + identifier
    old_label = dispatch.LABEL
    with native.consumer.file_lock(root/'docker-lifecycle.lock'):
        ledger = native.fence.load(root); native.fence.assert_detached(ledger)
        source_id = ledger['identifier']; _, source = native.fence.names(source_id, 'dispatcharr')
        source_path = native.volume_path(source_id, 'dispatcharr')
        source_before = native.shape(source_path/'db', True, (1000, 1000))
        dump_before = native.shape(source_path/'atlas-cold-copy.dump', owner=(1000, 1000))
        capture = native.pub.read_json(baseline/'CAPTURE.json')
        require(capture['ledger_sha256'] == native.consumer.document_sha(root/'DOCKER_LIFECYCLE.json')
            and native.shape(baseline/'dispatcharr-db', True, (0, 0)) == source_before)
        try:
            base.docker('volume', 'create', '--driver', 'local', '--label', base.LABEL+'='+identifier, target)
            target_path = native.volume_path(identifier, 'dispatcharr')
            require(not any(target_path.iterdir()))
            target_path.chmod(0o700); os.chown(target_path, 1000, 1000)
            dispatch.LABEL = native.fence.LABEL
            data, bootstrap = dispatch.payload(Path(__file__).resolve().parents[2])
            base.invoke(*dispatch.helper_arguments(base, helper, source, target, identifier, bootstrap, 'prepare'))
            item = dispatch.inspect_helper(base, helper, source, target, identifier, 'prepare')
            require(item['State']['Status'] == 'created' and not item['State']['Running']
                and item['HostConfig']['RestartPolicy']['Name'] == 'no'
                and not item['HostConfig'].get('AutoRemove') and not item['HostConfig'].get('Binds')
                and not item['HostConfig'].get('VolumesFrom'))
            require(native.fence.references(source) == {item['Id']} and native.fence.references(target) == {item['Id']})
            print('STRICT_DUMP_HELPER=running', flush=True)
            result = base.invoke('docker', 'start', '--attach', '--interactive', helper, input=data, timeout=180, check=False)
            if result.returncode:
                match = re.search(rb'DISPATCHARR_FIXTURE_HELPER=FAIL category=([a-z-]{1,80})', result.stderr)
                if match: print(match.group().decode(), flush=True)
            require(result.returncode == 0 and len(result.stdout) <= 4096)
            receipt = json.loads(result.stdout); validate_receipt(receipt)
            require(receipt['dump_sha256'] == dump_before['.'][2])
            stopped = dispatch.inspect_helper(base, helper, source, target, identifier, 'prepare')
            require(stopped['Id'] == item['Id']); dispatch.exited(stopped)
            # Exited helpers still reference volumes. Remove this exact stopped
            # ID without force or volume deletion before host capture resumes.
            base.docker('rm', item['Id'])
            native.fence.assert_detached(ledger)
            require(not native.fence.references(target))
            native.copy_tree(target_path/'db', baseline/'strict-incoming', True, (1000, 1000))
            require(native.shape(source_path/'db', True, (1000, 1000)) == source_before
                and native.shape(source_path/'atlas-cold-copy.dump', owner=(1000, 1000)) == dump_before)
            promote(native, baseline, baseline/'strict-incoming', receipt)
        finally:
            try: base.cleanup([helper], target, identifier)
            finally:
                dispatch.LABEL = old_label
                native.fence.assert_detached(ledger)
                require(native.shape(source_path/'db', True, (1000, 1000)) == source_before
                    and native.shape(source_path/'atlas-cold-copy.dump', owner=(1000, 1000)) == dump_before)
