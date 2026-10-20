"""Strict, private inspection candidates. Integration into action admission is pending.

Only explicitly bounded inspection representations are equivalent. All other
Config, HostConfig, effective mount and network fields remain in the model.
"""
import copy
import re
from pathlib import PurePosixPath
from atlas.maintenance_control import MaintenanceControlError

LABEL = 'io.project-atlas.create-only-profile'

def need(value, message):
    if not value:
        raise MaintenanceControlError(message)

def absolute(value):
    return isinstance(value, str) and value.startswith('/') and '..' not in PurePosixPath(value).parts

def semantic_model(native):
    result = copy.deepcopy(native)
    config, host = result['config'], result['host_config']
    env = config.get('Env', [])
    if env is None: env = []
    need(isinstance(env, list), 'inspection_environment_invalid')
    values = {}
    for entry in env:
        need(isinstance(entry, str) and '=' in entry, 'inspection_environment_invalid')
        name, value = entry.split('=', 1)
        need(name and name not in values, 'inspection_duplicate_environment')
        values[name] = value
    config['Env'] = [name + '=' + values[name] for name in sorted(values)]
    labels = config.get('Labels') or {}
    # Compose provenance paths, replaced-container ID and dependency summary are
    # generated metadata; immutable recipes independently retain actual settings.
    for key in ('com.docker.compose.project.environment_file', 'com.docker.compose.replace',
                'com.docker.compose.depends_on'):
        if key in labels:
            need(isinstance(labels[key], str), 'inspection_compose_metadata_invalid')
            labels.pop(key)
    config['Labels'] = labels
    oom = host.get('OomKillDisable')
    need(oom is None or type(oom) is bool, 'inspection_oom_control_invalid')
    if 'OomKillDisable' in host:
        host['OomKillDisable'] = False if oom is None else oom

    declared = {}
    def add(source, destination, readonly, propagation):
        need(absolute(source) and absolute(destination) and type(readonly) is bool
             and propagation in ('rprivate', 'private', 'rshared', 'shared', 'rslave', 'slave'),
             'inspection_bind_contract_invalid')
        need(destination not in declared, 'inspection_duplicate_mount_target')
        declared[destination] = {'Type': 'bind', 'Source': source, 'Target': destination,
                                'ReadOnly': readonly, 'BindOptions': {'Propagation': propagation}}
    binds = host.get('Binds')
    need(binds is None or isinstance(binds, list), 'inspection_binds_invalid')
    for value in binds or []:
        need(isinstance(value, str), 'inspection_bind_string_invalid')
        parts = value.split(':')
        need(len(parts) in (2, 3), 'inspection_bind_string_invalid')
        flags = parts[2].split(',') if len(parts) == 3 and parts[2] else []
        need(len(flags) == len(set(flags)) and set(flags) <= {'ro', 'rw', 'rprivate', 'private', 'rshared', 'shared', 'rslave', 'slave'}
             and not {'ro', 'rw'} <= set(flags), 'inspection_bind_flags_require_review')
        propagation = [flag for flag in flags if flag not in ('ro', 'rw')]
        need(len(propagation) <= 1, 'inspection_bind_propagation_invalid')
        add(parts[0], parts[1], 'ro' in flags, propagation[0] if propagation else 'rprivate')
    structured = host.get('Mounts')
    need(structured is None or isinstance(structured, list), 'inspection_structured_mounts_invalid')
    for mount in structured or []:
        need(isinstance(mount, dict) and set(mount) <= {'Type', 'Source', 'Target', 'ReadOnly', 'BindOptions'}
             and mount.get('Type') == 'bind', 'inspection_structured_mount_requires_review')
        options = mount.get('BindOptions', {})
        need(isinstance(options, dict) and set(options) <= {'Propagation'}, 'inspection_bind_options_require_review')
        add(mount.get('Source'), mount.get('Target'), mount.get('ReadOnly', False), options.get('Propagation', 'rprivate'))
    effective = []
    for mount in result['mounts']:
        need(mount.get('Type') == 'bind' and set(mount) <= {'Type', 'Source', 'Destination', 'Mode', 'RW', 'Propagation'},
             'inspection_effective_mount_requires_review')
        destination = mount['Destination']
        need(destination in declared and type(mount.get('RW')) is bool, 'inspection_effective_mount_undeclared')
        item = declared[destination]
        need(mount['Source'] == item['Source'] and mount['RW'] is (not item['ReadOnly'])
             and mount.get('Propagation') == item['BindOptions']['Propagation'], 'inspection_effective_mount_conflict')
        need(isinstance(mount.get('Mode', ''), str), 'inspection_effective_mode_invalid')
        flags = mount.get('Mode', '').split(',') if mount.get('Mode') else []
        need(len(flags) == len(set(flags)) and set(flags) <= {'ro', 'rw', item['BindOptions']['Propagation']}
             and not {'ro', 'rw'} <= set(flags), 'inspection_effective_mode_requires_review')
        need(('ro' not in flags or item['ReadOnly']) and ('rw' not in flags or not item['ReadOnly']),
             'inspection_effective_mode_conflict')
        mount['Mode'] = 'ro' if item['ReadOnly'] else 'rw'
        effective.append(mount)
    need(len(effective) == len(declared), 'inspection_effective_mount_coverage_differs')
    host['Binds'] = None
    host['Mounts'] = [declared[key] for key in sorted(declared)]
    result['mounts'] = sorted(effective, key=lambda item: item['Destination'])
    return result

def project_probe(row, mapping, role, nonce):
    """Undo only recorded isolation substitutions; port bindings are recipe-derived."""
    result = copy.deepcopy(row)
    names = mapping['containers'][role]
    need(result['Name'] == '/' + names['private'], 'inspection_probe_name_differs')
    need(result['Config']['Labels'].pop(LABEL, None) == nonce, 'inspection_probe_owner_differs')
    result['Name'] = '/' + names['original']
    result['Config']['Labels']['com.docker.compose.project'] = 'atlas-ingress'
    paths = {item['private']: item['original'] for item in mapping['binds'] if item['role'] == role}
    for mount in result['Mounts']:
        need(mount.get('Type') == 'bind' and mount['Source'] in paths, 'inspection_probe_mount_differs')
        mount['Source'] = paths[mount['Source']]
    host = result['HostConfig']
    for mount in host.get('Mounts') or []:
        need(mount.get('Type') == 'bind' and mount['Source'] in paths, 'inspection_probe_host_mount_differs')
        mount['Source'] = paths[mount['Source']]
    binds = []
    for bind in host.get('Binds') or []:
        source, separator, rest = bind.partition(':')
        need(separator and source in paths, 'inspection_probe_bind_differs')
        binds.append(paths[source] + separator + rest)
    if host.get('Binds') is not None:
        host['Binds'] = binds
    nets = {item['private']: item['original'] for item in mapping['networks'].values()}
    need(host.get('NetworkMode') in nets, 'inspection_probe_network_mode_differs')
    host['NetworkMode'] = nets[host['NetworkMode']]
    translated = {}
    for name, endpoint in result['NetworkSettings']['Networks'].items():
        need(name in nets, 'inspection_probe_network_differs')
        endpoint['Aliases'] = [names['original'] if alias == names['private'] else alias
                               for alias in endpoint.get('Aliases') or []]
        translated[nets[name]] = endpoint
    result['NetworkSettings']['Networks'] = translated
    need(not host.get('PortBindings') and not host.get('PublishAllPorts'), 'inspection_probe_publishes_ports')
    ports = {}
    for port in mapping['ports'][role]:
        need(isinstance(port, dict) and set(port) <= {'mode', 'target', 'published', 'protocol', 'host_ip'}
             and port.get('mode', 'ingress') == 'ingress' and type(port.get('target')) is int
             and 1 <= port['target'] <= 65535 and port.get('protocol', 'tcp') in ('tcp', 'udp'),
             'inspection_port_recipe_requires_review')
        published = str(port.get('published', ''))
        need(published.isdecimal() and 1 <= int(published) <= 65535, 'inspection_port_range_requires_review')
        address = port.get('host_ip', '')
        need(isinstance(address, str), 'inspection_port_address_invalid')
        key = str(port['target']) + '/' + port.get('protocol', 'tcp')
        ports.setdefault(key, []).append({'HostIp': address, 'HostPort': published})
    host['PortBindings'] = ports
    return result
