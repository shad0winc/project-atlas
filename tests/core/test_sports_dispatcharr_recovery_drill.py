"""Exercise isolation boundaries and failure paths without Docker or production."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


driver = load('dispatcharr_restart_driver', ROOT / 'scripts/diagnostics/sports-dispatcharr-recovery-drill.py')
helper = load('dispatcharr_restart_helper', ROOT / 'scripts/lib/sports-dispatcharr-recovery-drill.py')
adapter = load('dispatcharr_restart_adapter', ROOT / 'scripts/lib/sports-postgres-prepare.py')


class DispatcharrRestartTests(unittest.TestCase):
    def test_helper_mounts_source_readonly_and_only_new_target_writable(self):
        base = driver.utilities(ROOT)
        for mode in ('prepare', 'verify'):
            args = driver.helper_arguments(base, 'h', 'original', 'restored', 'id', 'bootstrap', mode,
                                           'a' * 64 if mode == 'verify' else None)
            mounts = [args[i + 1] for i, v in enumerate(args) if v == '--mount']
            self.assertEqual(mounts, ['type=volume,source=original,destination=/source,readonly,volume-nocopy',
                'type=volume,source=restored,destination=/target,' + ('readonly,' if mode == 'verify' else '') + 'volume-nocopy'])
            for option in ('--network=none', '--read-only', '--cap-drop=ALL', '--user=1000:1000', '--log-driver=none'):
                self.assertIn(option, args)
            self.assertFalse(any('type=bind' in v or '/mnt/' in v or '--env-file' in v for v in args))
        for mode, digest in (('invalid', None), ('verify', None), ('verify', '../path'), ('prepare', 'a' * 64)):
            with self.subTest(mode=mode, digest=digest), self.assertRaises(RuntimeError):
                driver.helper_arguments(base, 'h', 's', 't', 'id', 'bootstrap', mode, digest)

    def test_initializer_has_only_fresh_volume_and_chown_capability(self):
        base = driver.utilities(ROOT)
        args = driver.initialize_arguments(base, 'init', 'fresh', 'id')
        self.assertEqual([args[i+1] for i,v in enumerate(args) if v=='--mount'],
                         ['type=volume,source=fresh,destination=/target,volume-nocopy'])
        self.assertEqual([v for v in args if v.startswith('--cap-add')], ['--cap-add=CHOWN'])
        self.assertIn('--read-only', args)
        self.assertIn('not any(p.iterdir())', driver.INIT)

    def item(self):
        return {'Image': 'pinned', 'Config': {'Labels': {driver.LABEL: 'id'}, 'User': '1000:1000', 'Entrypoint': ['python3']},
            'HostConfig': {'ReadonlyRootfs': True, 'NetworkMode': 'none', 'Privileged': False, 'PortBindings': {}},
            'Mounts': [{'Type': 'volume', 'Name': 'src', 'Destination': '/source', 'RW': False},
                       {'Type': 'volume', 'Name': 'dst', 'Destination': '/target', 'RW': True}]}

    def test_attestation_rejects_wrong_mounts_identity_image_and_network(self):
        base = Mock(); base.IMAGE = 'pinned'
        good = self.item(); base.inspect.return_value = good
        driver.inspect_helper(base, 'h', 'src', 'dst', 'id', 'prepare')
        for change in ('source-writable', 'target-wrong', 'bind', 'extra', 'duplicate', 'user', 'image', 'network', 'label', 'entrypoint', 'rootfs', 'ports'):
            item = copy.deepcopy(good)
            if change == 'source-writable': item['Mounts'][0]['RW'] = True
            if change == 'target-wrong': item['Mounts'][1]['Name'] = 'production'
            if change == 'bind': item['Mounts'][1]['Type'] = 'bind'
            if change == 'extra': item['Mounts'].append(item['Mounts'][0])
            if change == 'duplicate': item['Mounts'][1]['Destination'] = '/source'
            if change == 'user': item['Config']['User'] = '0:0'
            if change == 'image': item['Image'] = 'unpinned'
            if change == 'network': item['HostConfig']['NetworkMode'] = 'host'
            if change == 'label': item['Config']['Labels'][driver.LABEL] = 'other'
            if change == 'entrypoint': item['Config']['Entrypoint'] = ['app']
            if change == 'rootfs': item['HostConfig']['ReadonlyRootfs'] = False
            if change == 'ports': item['HostConfig']['PortBindings'] = {'9191/tcp':[{}]}
            base.inspect.return_value = item
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                driver.inspect_helper(base, 'h', 'src', 'dst', 'id', 'prepare')
        base.inspect.return_value = good
        with self.assertRaises(RuntimeError): driver.inspect_helper(base, 'h', 'src', 'dst', 'id', 'verify')

    def test_explicit_fast_stop_must_succeed_before_docker_stop(self):
        base = Mock(); base.docker.side_effect = RuntimeError('stop-failed')
        with self.assertRaises(RuntimeError): driver.stop(base, 'app', 'vol', 'id')
        self.assertEqual(base.docker.call_count, 1)
        self.assertEqual(base.docker.call_args.args[:4], ('exec', '--user', '1000:1000', 'app'))
        self.assertIn('fast', base.docker.call_args.args)

    def test_kill_oom_running_and_nonzero_exit_fail_stop(self):
        good = {'Status':'exited', 'Running':False, 'Pid':0, 'ExitCode':0, 'OOMKilled':False}
        for change in ({'ExitCode':137}, {'OOMKilled':True}, {'Running':True}, {'Pid':1}, {'Status':'running'}):
            base = Mock(); base.owned_container.return_value = {'State': {**good, **change}}
            with self.subTest(change=change), self.assertRaises(RuntimeError): driver.stop(base, 'a', 'v', 'id')
        base = Mock(); base.owned_container.return_value = {'State':good}
        driver.stop(base, 'a', 'v', 'id'); self.assertEqual(base.docker.call_count, 2)

    def test_helper_refuses_wrong_identity_scope_and_digest_before_read(self):
        for uid, gid, flag, mode, expected in ((0,0,'1','prepare',None), (1000,999,'1','prepare',None),
            (1000,1000,'0','prepare',None), (1000,1000,'1','verify','bad'), (1000,1000,'1','prepare','a'*64)):
            with patch.object(helper.os,'geteuid',return_value=uid), patch.object(helper.os,'getegid',return_value=gid), \
                 patch.dict(os.environ,{'ATLAS_DISPATCHARR_DRILL':flag}), patch.object(adapter,'directory') as directory:
                with self.assertRaises(adapter.PrepareError): helper.run(adapter, mode, expected)
                directory.assert_not_called()

    def test_changed_source_blocks_verify_without_starting_any_cluster(self):
        fake = Mock(wraps=adapter)
        fake.directory.return_value = Path('/source/db')
        fake.tools_for.return_value = ('17', {'pg_ctl':Path('/bin/pg_ctl')})
        fake.cluster_digest.return_value = 'b' * 64
        fake.archive_digest.return_value = 'c' * 64
        fake.cold_state.return_value = None
        with patch.object(helper.os,'geteuid',return_value=1000), patch.object(helper.os,'getegid',return_value=1000), \
             patch.dict(os.environ,{'ATLAS_DISPATCHARR_DRILL':'1'}):
            with self.assertRaisesRegex(adapter.PrepareError, 'drill-source-changed'):
                helper.run(fake, 'verify', 'a' * 64)
        fake.prepare.assert_not_called(); fake.command.assert_not_called()

    def test_readonly_verification_checks_both_clean_clusters_and_bound_dump(self):
        fake = Mock(wraps=adapter)
        fake.directory.side_effect = lambda p:p
        fake.tools_for.return_value = ('17', {'pg_ctl':Path('/bin/pg_ctl')})
        fake.cluster_digest.return_value = 'a' * 64
        fake.archive_digest.return_value = 'b' * 64
        fake.cold_state.return_value = None
        with patch.object(helper.os,'geteuid',return_value=1000), patch.object(helper.os,'getegid',return_value=1000), \
             patch.dict(os.environ,{'ATLAS_DISPATCHARR_DRILL':'1'}):
            receipt = helper.run(fake,'verify','a'*64)
        self.assertEqual(fake.cold_state.call_count,3)
        fake.prepare.assert_not_called(); fake.command.assert_not_called()
        driver.validate_receipt(receipt,'verify',receipt)

    def test_receipts_reject_false_claims_wrong_types_or_changed_hashes(self):
        good = {'version':1,'scope':'synthetic-dispatcharr-only','mode':'verify', 'source_sha256':'a'*64,
            'dump_sha256':'b'*64,'cold_source_unchanged':True,'restored_cluster_stopped':True,
            'production_state_access':False,'live_restore_enabled':False}
        driver.validate_receipt(good,'verify',good)
        for change in ({'version':True}, {'live_restore_enabled':True}, {'cold_source_unchanged':1},
                       {'dump_sha256':'c'*64}, {'source_sha256':'bad'}, {'extra':True}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                driver.validate_receipt({**good,**change},'verify',good)

    def test_marker_queries_are_fixed_and_require_stale_object_absence(self):
        for marker, change in (('snapshot',False), ('persisted-after-restore',True), ('persisted-after-restore',False)):
            code = driver.marker_code(marker,change); compile(code,'<marker>','exec')
            self.assertIn('atlas_post_dump_stale', code)
            self.assertIn('ON_ERROR_STOP=1', code)
        with self.assertRaises(RuntimeError): driver.marker_code("';DROP TABLE x")
        self.assertIn("'127.0.0.1',9191", driver.HTTP_READY)
        self.assertIn("'GET','/'", driver.HTTP_READY)

    def test_error_categories_never_print_arbitrary_tool_or_sql_details(self):
        for error, expected in ((RuntimeError('private-value'),'helper-failed'),
            (adapter.PrepareError('cluster-not-cleanly-stopped'),'cluster-not-cleanly-stopped'),
            (adapter.PrepareError('private\nvalue'),'helper-failed')):
            err = io.StringIO()
            with patch.object(helper.sys,'argv',['helper','prepare']), patch.object(helper,'run',side_effect=error), contextlib.redirect_stderr(err):
                self.assertEqual(helper.main(adapter),1)
            self.assertEqual(err.getvalue(),'DISPATCHARR_FIXTURE_HELPER=FAIL category='+expected+'\n')

    def test_production_observation_ignores_only_mount_list_order(self):
        mounts = [{'Type':'volume','Name':'state','Destination':'/data','RW':True},
                  {'Type':'volume','Name':'policy','Destination':'/policy','RW':False}]
        base = Mock()
        base.observation.return_value = [('writer','image',42,'start',mounts)]
        before = driver.observation(base)
        base.observation.return_value = [('writer','image',42,'start',list(reversed(mounts)))]
        self.assertEqual(driver.observation(base),before)
        # Sorting must neither erase fields nor deduplicate mounts.
        for field, value in (('Type','bind'),('Name','other'),('Destination','/elsewhere'),('RW',False)):
            changed = copy.deepcopy(mounts); changed[0][field] = value
            base.observation.return_value = [('writer','image',42,'start',changed)]
            with self.subTest(field=field): self.assertNotEqual(driver.observation(base),before)
        base.observation.return_value = [('writer','image',42,'start',mounts + [mounts[0]])]
        self.assertNotEqual(driver.observation(base),before)
        for image, pid, started in (('new-image',42,'start'),('image',43,'start'),('image',42,'restart')):
            base.observation.return_value = [('writer',image,pid,started,mounts)]
            with self.subTest(image=image,pid=pid,started=started):
                self.assertNotEqual(driver.observation(base),before)

    def lifecycle(self, fail_restart=False, fail_first_cleanup=False):
        base = Mock(); base.IMAGE = 'pinned'; base.DEPLOYMENT = 'expected'
        base.observation.return_value = [('stable-container','pinned-image',123,'stable-start',[])]
        base.app_arguments.side_effect = lambda app, vol, ident:['docker','create','app',app,vol]
        base.container_options.return_value = ['--network=none']
        state = {'Status':'exited','Running':False,'Pid':0,'OOMKilled':False,'ExitCode':0}
        base.owned_container.return_value = {'State':state}
        receipt = {'version':1,'scope':'synthetic-dispatcharr-only','mode':'prepare',
            'source_sha256':'a'*64,'dump_sha256':'b'*64,'cold_source_unchanged':True,
            'restored_cluster_stopped':True,'production_state_access':False,'live_restore_enabled':False}
        def invoke(*args, **kwargs):
            if args[0]=='git': return subprocess.CompletedProcess(args,0,driver.HEAD.encode(),b'')
            if args[:3]==('docker','start','--attach'):
                mode = 'verify' if '-verify-' in args[-1] else 'prepare'
                return subprocess.CompletedProcess(args,0,json.dumps({**receipt,'mode':mode}).encode(),b'')
            return subprocess.CompletedProcess(args,0,b'',b'')
        base.invoke.side_effect = invoke
        def docker(*args, **kwargs):
            if args[:2]==('image','inspect'):
                return json.dumps([{'Id':'pinned','Config':{'Entrypoint':['/app/docker/entrypoint.sh'],'Cmd':None,'Volumes':None}}])
            if args[:2]==('start','--attach'): return 'volume-initialized'
            if args[0]=='exec':
                code=args[-1]
                if code=='snapshot-code': return 'snapshot-captured'
                if 'stale-created' in code: return 'stale-created'
                return 'marker-valid'
            return ''
        base.SNAPSHOT='snapshot-code'; base.docker.side_effect=docker
        if fail_first_cleanup: base.cleanup.side_effect=[RuntimeError('cleanup-failed'),None]
        pointer=Mock(); pointer.is_file.return_value=True; pointer.is_symlink.return_value=False
        pointer.read_bytes.return_value=b'expected'
        real_path=Path
        def paths(value):
            return pointer if str(value)=='/mnt/storage/configs/atlas/deployments/current' else real_path(value)
        out=io.StringIO(); err=io.StringIO()
        with patch.object(driver,'Path',side_effect=paths), patch.object(driver,'utilities',return_value=base), \
             patch.object(driver,'payload',return_value=(b'payload','bootstrap')), \
             patch.object(driver,'inspect_helper',return_value={'State':state}), \
             patch.object(driver,'stop') as stop, \
             patch.object(driver,'wait_ready',side_effect=[None,RuntimeError('restart-failed')] if fail_restart else None), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            if fail_restart or fail_first_cleanup:
                with self.assertRaises(RuntimeError): driver.run()
            else: driver.run()
        return base,stop,out.getvalue()

    def test_lifecycle_uses_second_volume_and_checks_two_restored_starts(self):
        base,stop,output=self.lifecycle()
        apps=base.app_arguments.call_args_list
        self.assertEqual(len(apps),2)
        self.assertNotEqual(apps[0].args[1], apps[1].args[1])
        self.assertEqual(stop.call_count,3)
        # Only the restored app is restarted; the original cold fixture stays stopped.
        starts=[c.args[1] for c in base.docker.call_args_list if c.args[:1]==('start',) and len(c.args)==2]
        self.assertEqual(starts,[apps[0].args[0],apps[1].args[0],apps[1].args[0]])
        self.assertEqual(base.cleanup.call_count,2)
        self.assertEqual(base.observation.call_count,2)
        self.assertIn('SYNTHETIC_DISPATCHARR_RECOVERY_DRILL=PASS',output)

    def test_failed_application_restart_cleans_both_volumes_and_never_reports_pass(self):
        base,stop,output=self.lifecycle(fail_restart=True)
        self.assertEqual(base.cleanup.call_count,2)
        self.assertEqual(base.observation.call_count,2)
        self.assertNotIn('SYNTHETIC_DISPATCHARR_RECOVERY_DRILL=PASS',output)

    def test_first_cleanup_failure_still_cleans_second_volume_and_checks_production(self):
        base,stop,output=self.lifecycle(fail_first_cleanup=True)
        self.assertEqual(base.cleanup.call_count,2)
        self.assertEqual(base.observation.call_count,2)
        self.assertNotIn('SYNTHETIC_DISPATCHARR_RECOVERY_DRILL=PASS',output)

    def test_payload_pins_and_bootstrap_compile(self):
        data, bootstrap = driver.payload(ROOT)
        compile(bootstrap,'<bootstrap>','exec')
        self.assertEqual(set(json.loads(data)),{'adapter','helper'})
        self.assertEqual(hashlib.sha256((ROOT/'scripts/lib/sports-dispatcharr-recovery-drill.py').read_bytes()).hexdigest(),driver.HELPER_SHA)
        driver.utilities(ROOT)


if __name__ == '__main__': unittest.main()
