"""Detach exactly owned disposable Docker apps before fixture journal recovery.

Serial trusted drill controller only; no global Docker admission lock. Native
volumes and the cooperative filesystem journal are separate fixtures here.
"""
import importlib.util
import json
from pathlib import Path
import re
import subprocess

_spec = importlib.util.spec_from_file_location('lifecycle_consumption',
    Path(__file__).with_name('sports-recovery-consumption.py'))
consumption = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(consumption)
pub = consumption.publication
LABEL = 'io.project-atlas.recovery-lifecycle-drill'
IMAGES = {
    'dispatcharr': 'sha256:e5d4b045b51519be4142a7baf7da6750ad33f80dcb0a77b8832c2ce930c6fe12',
    'teamarr': 'sha256:ecec625df0a029cddecf72fcb86d0d2eb9c16ce14f9377b1ddc0954bba4e2ec7',
}
DESTINATIONS = {'dispatcharr': '/data', 'teamarr': '/app/data'}
STAGES = ('armed', 'pg-clean', 'stopped', 'detaching', 'detached')


class LifecycleError(ValueError):
    pass


def require(value):
    if not value: raise LifecycleError('Disposable Docker lifecycle fence held')


def checkpoint(name):
    """Test seam after each durable transition or container removal."""


def command(*args, timeout=30):
    result = subprocess.run(['docker', *args], capture_output=True, timeout=timeout)
    require(result.returncode == 0 and len(result.stdout) <= 1048576)
    return result.stdout.decode().strip()


def names(identifier, role):
    require(isinstance(identifier, str) and re.fullmatch('[a-f0-9]{32}', identifier) is not None)
    require(role in IMAGES)
    stem = 'atlas-lifecycle-drill-' + role + '-'
    return stem + 'app-' + identifier, stem + 'data-' + identifier


def volume(identifier, role):
    name, data = names(identifier, role)
    rows = json.loads(command('volume', 'inspect', data))
    require(len(rows) == 1)
    item = rows[0]
    require(item['Name'] == data and item['Driver'] == 'local'
        and not item.get('Options') and item.get('Scope') == 'local'
        and (item.get('Labels') or {}).get(LABEL) == identifier)
    return data


def inventory():
    # A successful daemon/list response is required: failed inspect is never
    # interpreted as proof that a container is absent.
    require(bool(command('info', '--format', '{{.ServerVersion}}')))
    rows = command('ps', '-a', '--no-trunc', '--format', '{{.ID}}|{{.Names}}')
    result = {}
    for line in rows.splitlines():
        identifier, name = line.split('|')
        require(re.fullmatch('[a-f0-9]{64}', identifier) is not None and identifier not in result)
        result[identifier] = name
    return result


def references(data):
    result = command('ps', '-a', '--no-trunc', '--filter', 'volume=' + data, '--format', '{{.ID}}')
    rows = result.splitlines()
    require(len(rows) == len(set(rows)) and all(re.fullmatch('[a-f0-9]{64}', row) for row in rows))
    return set(rows)


def inspect_app(identifier, role, target, epoch=None):
    name, data = names(identifier, role)
    rows = json.loads(command('inspect', target)); require(len(rows) == 1)
    item = rows[0]; config = item['Config']; host = item['HostConfig']; state = item['State']
    require(item['Name'] == '/' + name and item['Image'] == IMAGES[role]
        and re.fullmatch('[a-f0-9]{64}', item['Id']) is not None
        and (config.get('Labels') or {}).get(LABEL) == identifier and config['User'] == '0:0'
        and host['NetworkMode'] == 'none' and not host.get('Privileged')
        and not host.get('PortBindings') and not host.get('PublishAllPorts')
        and not host.get('AutoRemove') and not host.get('VolumesFrom')
        and not host.get('Binds') and not host.get('ReadonlyRootfs')
        and host.get('PidMode', '') == '' and host.get('UsernsMode', '') == ''
        and host.get('IpcMode') == 'private' and set(host.get('Tmpfs') or {}) == {'/tmp'}
        and host['RestartPolicy']['Name'] == 'no' and item['RestartCount'] == 0
        and not state['OOMKilled'] and not state.get('Dead') and not state.get('Paused')
        and not state.get('Restarting'))
    image = json.loads(command('image', 'inspect', IMAGES[role]))
    require(len(image) == 1 and image[0]['Id'] == IMAGES[role]
        and config.get('Entrypoint') == image[0]['Config'].get('Entrypoint')
        and config.get('Cmd') == image[0]['Config'].get('Cmd'))
    mounts = [row for row in item['Mounts'] if row['Type'] != 'tmpfs']
    require(len(mounts) == 1 and mounts[0]['Type'] == 'volume'
        and mounts[0]['Name'] == data and mounts[0]['Destination'] == DESTINATIONS[role]
        and mounts[0]['RW'] is True)
    actual = {'id': item['Id'], 'started_at': state['StartedAt']}
    require(isinstance(actual['started_at'], str) and actual['started_at'] not in ('', '0001-01-01T00:00:00Z'))
    if epoch is not None: require(actual == epoch)
    require((state['Status'] == 'running' and state['Running'] is True and state['Pid'] > 0)
        or (state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0
            and state['ExitCode'] in (0, 143)))
    return actual, state['Running']


def binding(root):
    return {'plan': consumption.document_sha(root/'transaction/PLAN.json'),
            'exposure': consumption.document_sha(root/'consumption/EXPOSURE.json')}


def save(root, ledger, stage):
    ledger['stage'] = stage
    pub.write_json(root/'DOCKER_LIFECYCLE.json', ledger)
    checkpoint(stage)


def load(root):
    ledger = pub.read_json(root/'DOCKER_LIFECYCLE.json')
    require(isinstance(ledger, dict) and set(ledger) == {'version', 'scope', 'identifier', 'binding', 'apps', 'stage'}
        and type(ledger['version']) is int and ledger['version'] == 1
        and ledger['scope'] == 'disposable-apps-separate-journal'
        and ledger['stage'] in STAGES and ledger['binding'] == binding(root)
        and isinstance(ledger['apps'], dict) and set(ledger['apps']) == set(IMAGES))
    for role, epoch in ledger['apps'].items():
        names(ledger['identifier'], role)
        require(isinstance(epoch, dict) and set(epoch) == {'id', 'started_at'}
            and isinstance(epoch['id'], str) and re.fullmatch('[a-f0-9]{64}', epoch['id']) is not None
            and isinstance(epoch['started_at'], str) and bool(epoch['started_at']))
    require(len({epoch['id'] for epoch in ledger['apps'].values()}) == 2)
    return ledger


def arm(sandbox, identifier):
    root = consumption.scoped(sandbox)
    with consumption.file_lock(root/'docker-lifecycle.lock'), consumption.journal(root):
        require(consumption.load(root)[3] == 'open')
        path = root/'DOCKER_LIFECYCLE.json'
        require(not path.exists() and not path.is_symlink())
        apps = {}
        for role in IMAGES:
            name, data = names(identifier, role); volume(identifier, role)
            epoch, running = inspect_app(identifier, role, name)
            require(running and references(data) == {epoch['id']}); apps[role] = epoch
        save(root, {'version': 1, 'scope': 'disposable-apps-separate-journal',
            'identifier': identifier, 'binding': binding(root), 'apps': apps}, 'armed')


def pg_state(target):
    raw = command('exec', '--user', '1000:1000', '--env', 'LC_ALL=C', target,
        '/usr/lib/postgresql/17/bin/pg_controldata', '/data/db')
    rows = re.findall(r'^Database cluster state:\s*(.+)$', raw, re.M)
    require(len(rows) == 1 and rows[0] in {'in production', 'shut down'})
    return rows[0]


def assert_detached(ledger):
    require(ledger['stage'] == 'detached')
    present = inventory()
    for role, epoch in ledger['apps'].items():
        name, data = names(ledger['identifier'], role); volume(ledger['identifier'], role)
        require(epoch['id'] not in present and name not in present.values() and not references(data))


def detach(sandbox):
    root = consumption.scoped(sandbox)
    with consumption.file_lock(root/'docker-lifecycle.lock'):
        ledger = load(root); identifier = ledger['identifier']
        if ledger['stage'] == 'detached': assert_detached(ledger); return
        if ledger['stage'] in {'armed', 'pg-clean'}:
            # Validate BOTH fixtures and volume exclusivity before any stop.
            for role, epoch in ledger['apps'].items():
                volume(identifier, role)
                inspect_app(identifier, role, epoch['id'], epoch)
                require(references(names(identifier, role)[1]) == {epoch['id']})
            target = ledger['apps']['dispatcharr']['id']
            if ledger['stage'] == 'armed':
                require(inspect_app(identifier, 'dispatcharr', target, ledger['apps']['dispatcharr'])[1])
                if pg_state(target) == 'in production':
                    command('exec', '--user', '1000:1000', target,
                        '/usr/lib/postgresql/17/bin/pg_ctl', '-D', '/data/db', '-m', 'fast', '-w', '-t', '20', 'stop', timeout=30)
                require(pg_state(target) == 'shut down'); save(root, ledger, 'pg-clean')
            for role, epoch in ledger['apps'].items():
                _, running = inspect_app(identifier, role, epoch['id'], epoch)
                if running:
                    # After a retry, recheck native clean state before stopping
                    # an AIO object whose pg-clean intent was already durable.
                    if role == 'dispatcharr': require(pg_state(epoch['id']) == 'shut down')
                    command('stop', '--time', '35', epoch['id'], timeout=45)
                require(not inspect_app(identifier, role, epoch['id'], epoch)[1])
            save(root, ledger, 'stopped')
        if ledger['stage'] == 'stopped':
            for role, epoch in ledger['apps'].items():
                volume(identifier, role)
                require(not inspect_app(identifier, role, epoch['id'], epoch)[1])
                require(references(names(identifier, role)[1]) == {epoch['id']})
            save(root, ledger, 'detaching')
        require(ledger['stage'] == 'detaching')
        for role, epoch in ledger['apps'].items():
            name, data = names(identifier, role); volume(identifier, role)
            present = inventory()
            if epoch['id'] in present:
                require(not inspect_app(identifier, role, epoch['id'], epoch)[1])
                require(references(data) == {epoch['id']})
                # Never force removal: an unexpected running app must hold.
                command('rm', epoch['id']); checkpoint('removed:' + role)
            else: require(name not in present.values())
            require(not references(data))
        save(root, ledger, 'detached'); assert_detached(ledger)


def recover(sandbox):
    root = consumption.scoped(sandbox)
    with consumption.file_lock(root/'docker-lifecycle.lock'):
        ledger = load(root); assert_detached(ledger)
        consumption.recover(root)
        assert_detached(ledger)
