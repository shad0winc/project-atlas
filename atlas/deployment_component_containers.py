"""Bounded API/Portal/Caddy recreation with exact inspection profiles.

No public dispatcher or production admission is provided. Profiles must be prepared
and pinned separately; real-daemon canaries remain required before deployment.
"""
from __future__ import annotations

import copy
import json
import os
import pwd
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

from atlas.deployment_component_rollout import digest, observation, require
from atlas.deployment_publication_journal import encoded, read_file, safe_directory
from atlas.maintenance_control import MaintenanceControlError
from atlas.deployment_inspection_semantics import semantic_model

MODEL_SCHEMA = 'private-semantic-inspection-v1'
ROLES = ('api', 'portal', 'caddy')
PROJECT = 'atlas-ingress'
DOCKER = ('/usr/bin/docker', '--host', 'unix:///var/run/docker.sock')
COMPOSE_METADATA = ('com.docker.compose.config-hash', 'com.docker.compose.version',
                    'com.docker.compose.project.config_files', 'com.docker.compose.project.working_dir')


def image_id(value):return isinstance(value, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', value) is not None


def plain(value):return json.loads(encoded(value))


def container_model(row):
    """Preserve full engine config, host controls and mounts; normalize only identity metadata."""
    config = copy.deepcopy(row['Config'])
    labels = config.get('Labels') or {}
    role = labels.get('com.docker.compose.service')
    require(role in ROLES and row['Name'] == '/atlas-' + role
            and labels.get('com.docker.compose.project') == PROJECT
            and labels.get('com.docker.compose.container-number') == '1'
            and labels.get('com.docker.compose.oneoff') in ('False', 'false'), 'component_container_ownership_differs')
    require(image_id(row['Image']), 'component_image_identity_invalid')
    # Docker-generated hostname and configured image reference change on recreation.
    # The immutable image ID, container name and all other configuration are pinned.
    hostname = config.pop('Hostname', '')
    require(hostname in ('', row['Id'][:12], row['Name'].lstrip('/')), 'component_custom_hostname_requires_review')
    config.pop('Image', None)
    for key in COMPOSE_METADATA:labels.pop(key, None)
    if 'com.docker.compose.image' in labels:
        require(labels.pop('com.docker.compose.image') == row['Image'], 'component_compose_image_label_differs')
    config['Labels'] = labels
    networks = {}
    for name, value in row['NetworkSettings']['Networks'].items():
        aliases = [alias for alias in value.get('Aliases') or [] if alias not in (row['Id'], row['Id'][:12])]
        networks[name] = {'aliases': sorted(aliases), 'links': value.get('Links'),
                          'ipam_config': value.get('IPAMConfig'), 'driver_options': value.get('DriverOpts')}
    return semantic_model({'name': row['Name'], 'image': row['Image'], 'config': config, 'host_config': copy.deepcopy(row['HostConfig']),
            'mounts': sorted(copy.deepcopy(row['Mounts']), key=lambda item: json.dumps(item, sort_keys=True)), 'networks': networks})


def container_observation(row):
    model = container_model(row);state = row['State']
    require(state.get('Running') is True and not any(state.get(key) for key in ('Paused', 'Restarting', 'Dead', 'OOMKilled'))
            and state.get('Health', {}).get('Status') == 'healthy', 'component_not_healthy_running')
    require(isinstance(row['Id'], str) and re.fullmatch('[0-9a-f]{64}', row['Id'])
            and type(state.get('Pid')) is int and state['Pid'] > 0 and isinstance(state.get('StartedAt'), str)
            and bool(state['StartedAt']) and type(row.get('RestartCount')) is int and row['RestartCount'] >= 0,
            'component_process_identity_unavailable')
    return {'fingerprint': digest(model), 'identity': digest({'model': model, 'container_id': row['Id'],
        'pid': state['Pid'], 'started_at': state['StartedAt'], 'restart_count': row['RestartCount']})}


def inventory_fingerprint(rows, *, exclude_role=None):
    result = {}
    for row in rows:
        if exclude_role and row['Name'] == '/atlas-' + exclude_role:continue
        require(row['Id'] not in result, 'component_inventory_duplicate_id')
        state = {key: row['State'].get(key) for key in ('Running', 'Paused', 'Restarting', 'Dead', 'OOMKilled',
                                                      'Pid', 'StartedAt', 'FinishedAt')}
        result[row['Id']] = digest({key: row[key] for key in ('Id', 'Name', 'Image', 'Config', 'HostConfig', 'RestartCount')} |
            {'Mounts': sorted(row['Mounts'], key=lambda value: json.dumps(value, sort_keys=True)), 'State': state,
             'Networks': row['NetworkSettings']['Networks']})
    return result


def pinned_recipe(raw, images):
    """Pin images, require existing networks/volumes, and prevent implicit bind-directory creation."""
    value = json.loads(raw)
    require(isinstance(value, dict) and set(value) <= {'name', 'services', 'networks', 'volumes', 'secrets', 'configs'}
            and value.get('name') == PROJECT and set(value.get('services', {})) == set(ROLES)
            and set(images) == set(ROLES) and all(image_id(item) for item in images.values()), 'component_recipe_scope_invalid')
    require(not value.get('configs') and not value.get('secrets'), 'component_dynamic_config_resource_requires_review')
    for category in ('networks', 'volumes'):
        for name, resource in (value.get(category) or {}).items():
            require(isinstance(resource, dict), 'component_resource_definition_invalid')
            actual = resource.get('name', name)
            require(isinstance(actual, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', actual),
                    'component_resource_name_invalid')
            # Never let a component up create or reconfigure shared resources.
            value[category][name] = {'name': actual, 'external': True}
    for role in ROLES:
        service = value['services'][role]
        require(service.get('container_name') == 'atlas-' + role, 'component_recipe_container_name_differs')
        require(not any(key in service for key in ('build', 'develop', 'extends', 'profiles', 'env_file',
            'pre_start', 'post_start', 'pre_stop', 'post_stop', 'provider')), 'component_recipe_dynamic_action_refused')
        service['image'] = images[role]
        for mount in service.get('volumes', []):
            require(isinstance(mount, dict) and mount.get('type') in ('bind', 'volume', 'tmpfs'), 'component_recipe_mount_invalid')
            if mount['type'] == 'bind':
                source = Path(mount.get('source', ''))
                require(source.is_absolute() and '..' not in source.parts, 'component_recipe_bind_source_invalid')
                mount.setdefault('bind', {})['create_host_path'] = False
    def literal(item):
        if isinstance(item, str):require('$' not in item.replace('$$', ''), 'component_recipe_interpolation_refused')
        elif isinstance(item, list):
            for child in item:literal(child)
        elif isinstance(item, dict):
            for child in item.values():literal(child)
    literal(value)
    return value


class DockerBackend:
    """Local daemon only; callers never supply raw command strings."""
    @staticmethod
    def _run(args, *, timeout=30):
        try:
            result = subprocess.run(list(DOCKER) + args, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C',
                'COMPOSE_INTERACTIVE_NO_CLI': '1', 'COMPOSE_MENU': 'false',
                'HOME': pwd.getpwuid(os.geteuid()).pw_dir}, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise MaintenanceControlError('component_docker_command_uncertain') from None
        require(result.returncode == 0, 'component_docker_command_failed')
        return result.stdout
    def inventory(self):
        ids = self._run(['container', 'ls', '--all', '--quiet', '--no-trunc']).decode().split()
        require(ids and len(ids) <= 256 and all(re.fullmatch('[0-9a-f]{64}', value) for value in ids),
                'component_inventory_unavailable')
        rows = json.loads(self._run(['container', 'inspect', *sorted(ids)]))
        require({row['Id'] for row in rows} == set(ids) and len(rows) == len(ids), 'component_inventory_changed')
        return rows
    def image(self, reference):
        require(image_id(reference), 'component_image_reference_not_immutable')
        rows = json.loads(self._run(['image', 'inspect', reference]))
        require(len(rows) == 1 and rows[0]['Id'] == reference, 'component_local_image_missing')
        return rows[0]['Id']
    def dependencies(self, model):
        for network in model['networks']:
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', network), 'component_network_name_invalid')
            rows = json.loads(self._run(['network', 'inspect', network]))
            require(len(rows) == 1 and rows[0]['Name'] == network, 'component_network_missing')
        for mount in model['mounts']:
            if mount['Type'] == 'bind':
                path = Path(mount['Source'])
                require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
                        'component_bind_source_missing_or_linked')
            elif mount['Type'] == 'volume':
                require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', mount['Name']), 'component_volume_name_invalid')
                rows = json.loads(self._run(['volume', 'inspect', mount['Name']]))
                require(len(rows) == 1 and rows[0]['Name'] == mount['Name'] and rows[0]['Mountpoint'] == mount['Source'],
                        'component_named_volume_missing')
            else:require(mount['Type'] == 'tmpfs', 'component_mount_type_unknown')
        return True
    def recreate(self, recipe, role):
        require(role in ROLES and Path(recipe).is_absolute(), 'component_recreate_scope_invalid')
        return self._run(['compose', '--project-name', PROJECT, '--project-directory', str(Path(recipe).parent),
             '--env-file', '/dev/null', '-f', str(recipe), 'up', '--detach', '--no-deps', '--no-build',
             '--pull', 'never', '--force-recreate', '--wait', '--wait-timeout', '90', role], timeout=120) is not None


class ComponentContainerActions:
    def __init__(self, recipes, models, generation, *, held_guard, unrelated_guard, backend=None, runtime_root='/mnt/storage/configs/atlas'):
        require(set(recipes) == set(models) == {'target', 'rollback'} and callable(held_guard)
                and callable(unrelated_guard), 'component_container_adapter_incomplete')
        self.recipes, self.models = plain(recipes), plain(models)
        self.generation = Path(generation)
        require(self.generation.parent.parent == Path(runtime_root) / 'deployments/repairs'
                and self.generation.name == 'source', 'component_generation_path_invalid')
        self.held_guard, self.unrelated_guard = held_guard, unrelated_guard
        self.backend = backend or DockerBackend()
        self.fingerprints = {}
        for mode in ('target', 'rollback'):
            require(set(self.models[mode]) == set(ROLES), 'component_model_scope_invalid')
            self.fingerprints[mode] = {}
            for role, model in self.models[mode].items():
                require(set(model) == {'name', 'image', 'config', 'host_config', 'mounts', 'networks'}
                        and model['name'] == '/atlas-' + role and image_id(model['image']) and model['networks'],
                        'component_inspection_model_invalid')
                require(model['host_config'].get('Privileged') is False
                        and 'no-new-privileges:true' in (model['host_config'].get('SecurityOpt') or []),
                        'component_inspection_privilege_contract_differs')
                labels = model['config'].get('Labels') or {}
                health = model['config'].get('Healthcheck') or {}
                require(labels.get('com.docker.compose.project') == PROJECT
                        and labels.get('com.docker.compose.service') == role
                        and labels.get('com.docker.compose.container-number') == '1'
                        and labels.get('com.docker.compose.oneoff') in ('False', 'false')
                        and health.get('Test') and health['Test'][0] != 'NONE', 'component_model_ownership_or_health_missing')
                require(semantic_model(model) == model, 'component_inspection_model_not_canonical')
                self.fingerprints[mode][role] = digest(model)
            self._recipe(mode)
        require(all(self.fingerprints['target'][role] != self.fingerprints['rollback'][role] for role in ROLES),
                'component_before_after_models_overlap')

    def _held(self):
        require(self.held_guard() is True and self.unrelated_guard() is True, 'component_held_or_unrelated_boundary_changed')

    def _recipe(self, mode):
        item = self.recipes[mode]
        require(set(item) == {'path', 'sha256'}, 'component_recipe_pin_invalid')
        path = Path(item['path']);safe_directory(path.parent)
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and info.st_nlink == 1
                and not info.st_mode & 0o022 and read_file(path) == item['sha256'], 'component_recipe_changed')
        raw = read_file(path, limit=2 * 1024 * 1024)
        images = {role: model['image'] for role, model in self.models[mode].items()}
        value = json.loads(raw)
        require(pinned_recipe(raw, images) == value, 'component_execution_recipe_not_fully_pinned')
        return path

    def _rows(self):
        rows = self.backend.inventory()
        names = [row['Name'] for row in rows]
        require(len(names) == len(set(names)), 'component_inventory_duplicate_name')
        for role in ROLES:
            selected = [row for row in rows if row['Name'] == '/atlas-' + role]
            require(len(selected) == 1, 'component_container_missing_or_ambiguous')
            related = [row for row in rows if (row['Config'].get('Labels') or {}).get('com.docker.compose.project') == PROJECT
                       and (row['Config'].get('Labels') or {}).get('com.docker.compose.service') == role]
            require(len(related) == 1 and related[0]['Id'] == selected[0]['Id'], 'component_duplicate_compose_service')
        return rows

    def observe(self, role):
        require(role in ROLES, 'component_unknown_container_role');self._held()
        row = next(row for row in self._rows() if row['Name'] == '/atlas-' + role)
        result = container_observation(row);self._held();return result

    def _change(self, role, mode):
        require(role in ROLES and mode in ('target', 'rollback'), 'component_change_scope_invalid');self._held()
        before = self.observe(role)
        if before['fingerprint'] == self.fingerprints[mode][role]:return
        other = 'rollback' if mode == 'target' else 'target'
        require(before['fingerprint'] == self.fingerprints[other][role], 'component_change_precondition_unknown')
        recipe = self._recipe(mode);model = self.models[mode][role]
        require(self.backend.image(model['image']) == model['image'] and self.backend.dependencies(model) is True,
                'component_target_dependencies_unproven')
        inventory = inventory_fingerprint(self._rows(), exclude_role=role)
        self._held();require(self.observe(role) == before, 'component_container_changed_before_command')
        # Recheck artifacts immediately before issuing the only permitted mutation.
        require(self._recipe(mode) == recipe, 'component_recipe_identity_changed')
        require(self.backend.recreate(recipe, role) is True, 'component_recreate_result_uncertain')
        self._held()
        require(inventory_fingerprint(self._rows(), exclude_role=role) == inventory, 'component_unselected_runtime_changed')
        after = self.observe(role)
        require(after['fingerprint'] == self.fingerprints[mode][role] and after['identity'] != before['identity'],
                'component_replacement_not_proven')

    def apply(self, role):self._change(role, 'target')
    def rollback(self, role):self._change(role, 'rollback')
    def confirm(self, role, mode, expected):
        require(mode in ('apply', 'rollback') and role in ROLES, 'component_confirmation_scope_invalid')
        expected = observation(expected);desired = 'target' if mode == 'apply' else 'rollback'
        self._held();self._recipe(desired)
        require(expected['fingerprint'] == self.fingerprints[desired][role] and self.observe(role) == expected,
                'component_confirmation_identity_changed')
        again = self.observe(role);require(again == expected, 'component_confirmation_identity_changed')
        return again
    def verify(self, mode):
        require(mode in ('apply', 'rollback'), 'component_verification_scope_invalid')
        desired = 'target' if mode == 'apply' else 'rollback';self._held();self._recipe(desired)
        for role in ROLES:
            require(self.observe(role)['fingerprint'] == self.fingerprints[desired][role], 'component_final_model_differs')
        self._held();return True
    def source_inactive(self):
        self.verify('rollback');self._held()
        generation = PurePosixPath(str(self.generation))
        for row in self._rows():
            for mount in row['Mounts']:
                if mount['Type'] != 'bind':continue
                source = PurePosixPath(mount['Source'])
                require(not (source == generation or source in generation.parents or generation in source.parents),
                        'component_generation_still_mounted')
        self._held();return True


def validate_execution_render(previous, actual, images):
    """Compare reviewed recipe transformations; tolerate only empty external IPAM metadata."""
    expected, observed = plain(previous), plain(actual)
    require(set(images) == set(ROLES) and all(image_id(value) for value in images.values())
            and set(expected.get('services', {})) == set(observed.get('services', {})) == set(ROLES),
            'component_render_scope_invalid')
    for role in ROLES:
        expected['services'][role]['image'] = images[role]
        for mount in expected['services'][role].get('volumes', []):
            if mount['type'] == 'bind':mount.setdefault('bind', {})['create_host_path'] = False
    for category in ('networks', 'volumes'):
        for name, resource in (expected.get(category) or {}).items():
            expected[category][name] = {'name': resource.get('name', name), 'external': True}
    for config in (expected, observed):
        for role in ROLES:
            for mount in config['services'][role].get('volumes', []):
                if mount['type'] == 'bind':
                    options = mount.setdefault('bind', {})
                    value = options.get('create_host_path', False)
                    require(type(value) is bool, 'component_bind_creation_policy_not_boolean')
                    options['create_host_path'] = value
        for resource in (config.get('networks') or {}).values():
            if resource.get('external') is True and 'ipam' in resource:
                require(type(resource['ipam']) is dict and not resource['ipam'], 'component_external_ipam_not_empty')
                resource.pop('ipam')
    require(encoded(expected) == encoded(observed), 'component_execution_render_settings_differ')
    return True
