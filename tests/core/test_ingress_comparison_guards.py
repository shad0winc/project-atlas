"""Preserve ingress identity across Docker representation differences."""
from pathlib import Path
import copy,json,types,unittest
HELPER=Path(__file__).resolve().parents[2]/'scripts/lib/deployment-ingress-provenance.py'
E=types.ModuleType('comparison_guards_verifier');E.__file__=str(HELPER)
exec(compile(HELPER.read_bytes(),str(HELPER),'exec'),E.__dict__)
IMAGE='sha256:'+'a'*64
class CaddyUnsetUserTests(unittest.TestCase):

    def setUp(self):
        self.original_query = E.query
        self.original_mount_boundary = E.check_mount_boundaries
        self.addCleanup(setattr, E, 'query', self.original_query)
        self.addCleanup(setattr, E, 'check_mount_boundaries', self.original_mount_boundary)
        self.image = {'Id': IMAGE, 'Config': {'Cmd': ['caddy', 'run', '--config', '/etc/caddy/Caddyfile', '--adapter', 'caddyfile'], 'Entrypoint': None, 'WorkingDir': '/srv', 'User': None}}
        self.row = {'Image': IMAGE, 'Name': '/atlas-caddy', 'Config': copy.deepcopy(self.image['Config']), 'HostConfig': {'Privileged': False, 'SecurityOpt': ['no-new-privileges:true']}}
        self.row['Config']['User'] = ''
        self.boundaries = []
        self.ext = {'images': {}, 'caddy': {'image_id': IMAGE}}

    def check(self, module=E):
        module.query = lambda *args, **kwargs: json.dumps([self.image]).encode()
        module.check_mount_boundaries = lambda role, row, ext: self.boundaries.append(role)
        module.image_checks(types.SimpleNamespace(), 'caddy', self.row, self.ext, Path('/unused'))

    def test_image_null_container_empty_passes(self):
        self.check()

    def test_image_empty_container_null_passes(self):
        self.image['Config']['User'] = ''
        self.row['Config']['User'] = None
        self.check()

    def test_both_empty_pass(self):
        self.image['Config']['User'] = ''
        self.check()

    def test_both_null_pass(self):
        self.row['Config']['User'] = None
        self.check()

    def test_explicit_root_is_not_unset(self):
        self.row['Config']['User'] = 'root'
        with self.assertRaisesRegex(ValueError, 'default startup'):
            self.check()

    def test_explicit_numeric_root_is_not_unset(self):
        self.row['Config']['User'] = '0:0'
        with self.assertRaisesRegex(ValueError, 'default startup'):
            self.check()

    def test_explicit_nonroot_is_not_unset(self):
        self.row['Config']['User'] = '999:999'
        with self.assertRaisesRegex(ValueError, 'default startup'):
            self.check()

    def test_command_override_refuses(self):
        self.row['Config']['Cmd'] = ['other']
        with self.assertRaisesRegex(ValueError, 'default startup'):
            self.check()

    def test_entrypoint_override_refuses(self):
        self.row['Config']['Entrypoint'] = []
        with self.assertRaisesRegex(ValueError, 'default startup'):
            self.check()

    def test_working_directory_override_refuses(self):
        self.row['Config']['WorkingDir'] = '/'
        with self.assertRaisesRegex(ValueError, 'default startup'):
            self.check()

    def test_image_identity_change_refuses(self):
        self.image['Id'] = 'sha256:' + 'b' * 64
        with self.assertRaisesRegex(ValueError, 'image identity'):
            self.check()

    def test_security_boundary_remains_required(self):
        self.row['HostConfig']['SecurityOpt'] = []
        with self.assertRaisesRegex(ValueError, 'execution boundary'):
            self.check()

    def test_mount_boundary_validation_is_still_called(self):
        self.check()
        self.assertEqual(self.boundaries, ['caddy'])

    def test_explicit_identical_user_keeps_original_semantics(self):
        self.image['Config']['User'] = self.row['Config']['User'] = 'root'
        self.check()

class IngressMountIdentityTests(unittest.TestCase):

    def setUp(self):
        self.original_query = E.query
        self.original_mount_boundary = E.check_mount_boundaries
        self.addCleanup(setattr, E, 'query', self.original_query)
        self.addCleanup(setattr, E, 'check_mount_boundaries', self.original_mount_boundary)
        self.row = {'Id': 'a' * 64, 'Image': 'sha256:' + 'b' * 64, 'Name': '/atlas-api', 'Config': {'User': 'atlas', 'Cmd': ['uvicorn'], 'Env': ['A=1', 'B=2']}, 'HostConfig': {'ReadonlyRootfs': True, 'Privileged': False}, 'RestartCount': 0, 'Mounts': [{'Type': 'bind', 'Source': '/one', 'Destination': '/first', 'RW': False, 'Mode': 'ro', 'Propagation': 'rprivate'}, {'Type': 'bind', 'Source': '/two', 'Destination': '/second', 'RW': True, 'Mode': 'rw', 'Propagation': 'rprivate'}], 'State': {'Running': True, 'Health': {'Status': 'healthy'}, 'Pid': 123, 'StartedAt': '2026-10-20T22:37:00Z'}}

    def changed_mount(self, key, value):
        other = copy.deepcopy(self.row)
        other['Mounts'][0][key] = value
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_mount_permutation_is_identical(self):
        other = copy.deepcopy(self.row)
        other['Mounts'].reverse()
        self.assertEqual(E.state_identity(self.row), E.state_identity(other))

    def test_source_change_is_detected(self):
        self.changed_mount('Source', '/other')

    def test_destination_change_is_detected(self):
        self.changed_mount('Destination', '/other')

    def test_writable_change_is_detected(self):
        self.changed_mount('RW', True)

    def test_mode_change_is_detected(self):
        self.changed_mount('Mode', 'rw')

    def test_propagation_change_is_detected(self):
        self.changed_mount('Propagation', 'rshared')

    def test_type_change_is_detected(self):
        self.changed_mount('Type', 'volume')

    def test_additional_mount_field_is_detected(self):
        self.changed_mount('UnreviewedMetadata', {'flag': True})

    def test_added_mount_is_detected(self):
        other = copy.deepcopy(self.row)
        other['Mounts'].append({'Type': 'tmpfs', 'Destination': '/tmp'})
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_removed_mount_is_detected(self):
        other = copy.deepcopy(self.row)
        other['Mounts'].pop()
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_duplicate_mount_destination_refuses(self):
        self.row['Mounts'][1]['Destination'] = '/first'
        with self.assertRaisesRegex(ValueError, 'Duplicate Ingress mount target'):
            E.state_identity(self.row)

    def test_pid_change_is_detected(self):
        other = copy.deepcopy(self.row)
        other['State']['Pid'] = 456
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_start_time_change_is_detected(self):
        other = copy.deepcopy(self.row)
        other['State']['StartedAt'] = 'later'
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_restart_count_change_is_detected(self):
        other = copy.deepcopy(self.row)
        other['RestartCount'] = 1
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_configuration_change_is_detected(self):
        other = copy.deepcopy(self.row)
        other['Config']['Cmd'] = ['other']
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_other_lists_are_not_reordered(self):
        other = copy.deepcopy(self.row)
        other['Config']['Env'].reverse()
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_host_controls_change_is_detected(self):
        other = copy.deepcopy(self.row)
        other['HostConfig']['ReadonlyRootfs'] = False
        self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_container_and_image_identity_changes_are_detected(self):
        for key, value in (('Id', 'c' * 64), ('Image', 'sha256:' + 'd' * 64), ('Name', '/other')):
            other = copy.deepcopy(self.row)
            other[key] = value
            self.assertNotEqual(E.state_identity(self.row), E.state_identity(other))

    def test_unhealthy_or_nonrunning_or_missing_pid_refuses(self):
        for state in ({'Running': False}, {'Health': {'Status': 'unhealthy'}}, {'Paused': True}, {'Restarting': True}, {'Dead': True}, {'OOMKilled': True}, {'Pid': 0}):
            other = copy.deepcopy(self.row)
            other['State'].update(state)
            with self.assertRaises(ValueError):
                E.state_identity(other)

    def test_unset_caddy_user_correction_remains_integrated(self):
        image = {'Id': 'sha256:' + 'e' * 64, 'Config': {'Cmd': ['caddy', 'run'], 'Entrypoint': None, 'WorkingDir': '/srv', 'User': None}}
        row = {'Image': image['Id'], 'Name': '/atlas-caddy', 'Config': dict(image['Config'], User=''), 'HostConfig': {'Privileged': False, 'SecurityOpt': ['no-new-privileges:true']}}
        E.query = lambda *args, **kwargs: json.dumps([image]).encode()
        E.check_mount_boundaries = lambda *args: None
        E.image_checks(types.SimpleNamespace(), 'caddy', row, {'images': {}, 'caddy': {'image_id': image['Id']}}, Path('/unused'))

if __name__=='__main__':unittest.main()
