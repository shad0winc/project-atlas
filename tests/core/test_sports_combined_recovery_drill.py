"""Combined fixture boundaries and real private byte/metadata regressions."""
import copy
import contextlib
import io
import subprocess
import hashlib
import importlib.util
import json
import os
import sqlite3
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock,patch
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'modules/sports/src'))


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


driver=load('combined_driver',ROOT/'scripts/diagnostics/sports-combined-recovery-drill.py')
helper=load('combined_helper',ROOT/'scripts/lib/sports-combined-recovery-drill.py')
pub=load('combined_publication',ROOT/'scripts/lib/sports-recovery-publication.py')


class CombinedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.handles=('ds','old','ts','journal','dout','tout','meta')
        self.journal='/tmp/project-atlas-sports-publication.'+'a'*32

    def test_consumer_materialization_never_exposes_journal_as_writable(self):
        base=Mock();base.IMAGE='pinned';base.container_options.return_value=['--network=none','--restart=no']
        for mode in ('collect','stage','materialize','probe','verify-consumers','rollback'):
            args=driver.helper_arguments(base,'name','id','boot',mode,self.handles,self.journal)
            self.assertIn('--read-only',args);self.assertIn('--cap-drop=ALL',args)
            mounts=[args[i+1] for i,v in enumerate(args) if v=='--mount']
            self.assertFalse(any('type=bind' in v or '/mnt/' in v for v in args))
            journal=next(v for v in mounts if 'source=journal,' in v)
            self.assertEqual('readonly,' in journal,mode in {'materialize','probe','verify-consumers'})
            if mode in {'collect','stage','rollback'}:
                source=next(v for v in mounts if 'source=ds,' in v)
                self.assertIn('readonly,',source)
            if mode in {'stage','probe','rollback'}:
                self.assertIn('--user=1000:1000',args)
                self.assertFalse(any(v.startswith('--cap-add') for v in args))
        with self.assertRaises(RuntimeError):driver.mount_plan('unknown',self.handles,self.journal)

    def item(self):
        return {'Image':'pinned','Config':{'User':'0:0','Entrypoint':['python3'],'Labels':{driver.LABEL:'id'}},
            'HostConfig':{'ReadonlyRootfs':True,'NetworkMode':'none','Privileged':False,'PortBindings':{}},
            'Mounts':[{'Type':'volume','Name':v,'Destination':d,'RW':w}
                      for v,d,w in driver.mount_plan('materialize',self.handles,self.journal)]}

    def test_helper_attestation_rejects_writable_journal_wrong_identity_and_extra_mount(self):
        base=Mock();base.IMAGE='pinned';good=self.item();base.inspect.return_value=good
        driver.attest(base,'h','id','materialize',self.handles,self.journal)
        for change in ('journal','bind','volume','extra','user','label','image','network','rootfs','ports'):
            item=copy.deepcopy(good)
            if change=='journal':item['Mounts'][0]['RW']=True
            if change=='bind':item['Mounts'][1]['Type']='bind'
            if change=='volume':item['Mounts'][1]['Name']='production'
            if change=='extra':item['Mounts'].append(item['Mounts'][0])
            if change=='user':item['Config']['User']='1000:1000'
            if change=='label':item['Config']['Labels'][driver.LABEL]='other'
            if change=='image':item['Image']='other'
            if change=='network':item['HostConfig']['NetworkMode']='host'
            if change=='rootfs':item['HostConfig']['ReadonlyRootfs']=False
            if change=='ports':item['HostConfig']['PortBindings']={'9191/tcp':[{}]}
            base.inspect.return_value=item
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                driver.attest(base,'h','id','materialize',self.handles,self.journal)

    def test_deferred_cleanup_keeps_component_order_and_owned_identifiers(self):
        real_cleanup=Mock();base=types.SimpleNamespace(LABEL='old',inspect=Mock(),cleanup=real_cleanup)
        module=types.SimpleNamespace(utilities=lambda root:base)
        groups=[];driver.defer_cleanup(module,groups);wrapped=module.utilities(ROOT)
        wrapped.cleanup(('app','helper'),'source','id');wrapped.cleanup((),'target','id')
        real_cleanup.assert_not_called();self.assertEqual(len(groups),2)
        driver.cleanup_all(groups)
        self.assertEqual([c.args for c in real_cleanup.call_args_list],[(('app','helper'),'source','id'),((),'target','id')])

    def test_cleanup_attempts_remaining_resources_after_a_failure(self):
        first=Mock(side_effect=RuntimeError('failed'));second=Mock()
        with self.assertRaises(RuntimeError):driver.cleanup_all([(first,('app',),'one','id'),(second,(),'two','id')])
        second.assert_called_once_with((),'two','id')

    def test_reordered_mounts_compare_equal_but_changed_contents_are_preserved(self):
        mounts=[{'Destination':'/a','RW':True},{'Destination':'/b','RW':False}]
        original=Mock(side_effect=[{'Mounts':mounts},{'Mounts':list(reversed(mounts))}])
        wrapped=driver.normalize_inspect(original)
        self.assertEqual(wrapped('one'),wrapped('two'))
        changed=copy.deepcopy(mounts);changed[0]['RW']=False
        self.assertNotEqual(driver.normalize_inspect(lambda name:{'Mounts':changed})('x')['Mounts'],mounts)

    def test_receipts_cannot_claim_live_restore_or_pass_with_wrong_types(self):
        good={'version':1,'scope':'synthetic-combined-sports','mode':'stage','checks_passed':True,
              'production_state_access':False,'live_restore_enabled':False}
        driver.check_receipt(json.dumps(good).encode(),'stage')
        for change in ({'version':True},{'checks_passed':1},{'live_restore_enabled':True},
                       {'mode':'materialize'},{'extra':True},{'production_state_access':True}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                driver.check_receipt(json.dumps({**good,**change}).encode(),'stage')

    def test_helper_scope_identity_and_fixed_sandbox_guard_precede_mutation(self):
        for mode,uid,gid,flag,path in (('stage',0,0,'1',self.journal),('collect',1000,1000,'1',self.journal),
            ('stage',1000,999,'1',self.journal),('stage',1000,1000,'0',self.journal),
            ('stage',1000,1000,'1','/mnt/storage/live'),('unknown',1000,1000,'1',self.journal)):
            with patch.object(helper.os,'geteuid',return_value=uid),patch.object(helper.os,'getegid',return_value=gid), \
                 patch.dict(os.environ,{'ATLAS_COMBINED_DRILL':flag}),patch.object(helper,'stage') as stage:
                with self.assertRaises(ValueError):helper.run(mode,path)
                stage.assert_not_called()

    def test_root_export_byte_framing_matches_journal_and_checks_links_modes_owners(self):
        root=self.root/'source';root.mkdir(mode=0o700)
        f=root/'file';f.write_bytes(b'private-fixture');f.chmod(0o600)
        expected=pub.digest(root,True)
        original=Path.lstat
        def owner(path,*a,**k):
            result=original(path,*a,**k)
            attrs={name:getattr(result,name) for name in ('st_mode','st_nlink','st_size','st_ino','st_dev','st_mtime_ns','st_ctime_ns')}
            return types.SimpleNamespace(**attrs,st_uid=1000,st_gid=1000)
        with patch.object(Path,'lstat',owner):self.assertEqual(helper.tree_digest(root,True),expected)
        f.chmod(0o644)
        with patch.object(Path,'lstat',owner),self.assertRaises(ValueError):helper.tree_digest(root,True)
        f.chmod(0o600);(root/'link').symlink_to(f)
        with self.assertRaises(ValueError):helper.content_shape(root,True)

    def test_copy_owned_keeps_exact_bytes_and_assigns_consumer_modes(self):
        source=self.root/'source';source.mkdir(mode=0o700)
        (source/'refresh.json').write_bytes(b'{"version":1,"enabled":false}\n')
        (source/'refresh.json').chmod(0o600)
        before=helper.content_shape(source,True);target=self.root/'target'
        with patch.object(helper.os,'chown') as chown:
            helper.copy_owned(source,target,0,1000,True,0o750,0o640)
        self.assertEqual(helper.content_shape(target,True),before)
        self.assertEqual(target.stat().st_mode&0o777,0o750)
        self.assertEqual((target/'refresh.json').stat().st_mode&0o777,0o640)
        self.assertEqual(chown.call_count,2)
        with patch.object(helper.os,'chown'),self.assertRaises(FileExistsError):
            helper.copy_owned(source,target,0,1000,True)

    def test_byte_and_entry_budgets_hardlinks_and_unstable_sources_are_rejected(self):
        source=self.root/'f';source.write_bytes(b'abc');source.chmod(0o600)
        with patch.object(helper,'LIMIT',2),self.assertRaises(ValueError):helper.content_shape(source)
        os.link(source,self.root/'hard')
        with self.assertRaises(ValueError):helper.content_shape(source)
        (self.root/'hard').unlink()
        with self.assertRaises(ValueError):helper.file_bytes(source,2)

    def test_real_metadata_alias_and_attempt_state_distinguishes_generations(self):
        helper.metadata(self.root/'old',111,'2475455')
        helper.metadata(self.root/'new',123,'2475454')
        helper.check_metadata(self.root/'old',111,'2475455')
        helper.check_metadata(self.root/'new',123,'2475454')
        with self.assertRaises(ValueError):helper.check_metadata(self.root/'new',111,'2475455')

    def test_all_five_surfaces_export_together_without_changing_journal(self):
        journal=self.root/'journal';current=journal/'current';current.mkdir(parents=True,mode=0o700)
        for name in helper.MEMBERS:
            path=current/name
            if name in helper.DIRECTORIES:path.mkdir(mode=0o700)
        (current/'dispatcharr-db/PG_VERSION').write_bytes(b'17\n')
        (current/'dispatcharr-db/PG_VERSION').chmod(0o600)
        for name,raw in (('dispatcharr-jwt',b'synthetic-jwt'),('teamarr-db',b'synthetic-snapshot')):
            (current/name).write_bytes(raw);(current/name).chmod(0o600)
        # Real metadata and policy content travel through the same export operation.
        md=current/'sports-metadata';md.rmdir();helper.metadata(md,123,'2475454')
        (current/'sports-metadata-policy/refresh.json').write_bytes(b'{"version":1,"enabled":false}\n')
        (current/'sports-metadata-policy/refresh.json').chmod(0o600)
        hashes={name:pub.digest(current/name,name in helper.DIRECTORIES) for name in helper.MEMBERS}
        value={'surfaces':[{'surface':name,'new_sha256':digest} for name,digest in hashes.items()],
               'jwt_sha256':helper.file_sha(current/'dispatcharr-jwt')}
        mapped={name:self.root/('out-'+str(i)) for i,name in enumerate(('/dispatch-target','/team-target','/metadata-target'))}
        for path in mapped.values():path.mkdir(mode=0o700)
        real_path=Path
        def path(value):
            for prefix,destination in mapped.items():
                if str(value)==prefix or str(value).startswith(prefix+'/'):
                    return destination/str(value)[len(prefix):].lstrip('/')
            return real_path(value)
        with patch.object(helper,'receipt',return_value=value),patch.object(helper,'tree_digest',side_effect=pub.digest), \
             patch.object(helper,'Path',side_effect=path),patch.object(helper.os,'chown'):
            helper.materialize(journal)
        self.assertEqual(hashes,{name:pub.digest(current/name,name in helper.DIRECTORIES) for name in helper.MEMBERS})
        self.assertEqual(helper.content_shape(current/'dispatcharr-db',True),helper.content_shape(mapped['/dispatch-target']/'db',True))
        self.assertEqual(helper.file_sha(current/'dispatcharr-jwt'),helper.file_sha(mapped['/dispatch-target']/'jwt'))
        self.assertEqual(helper.file_sha(current/'teamarr-db'),helper.file_sha(mapped['/team-target']/'teamarr.db'))
        helper.check_metadata(mapped['/metadata-target']/'sports-metadata',123,'2475454')
        # Running consumers may change their copies, but never journal snapshots.
        (mapped['/dispatch-target']/'db/PG_VERSION').write_bytes(b'consumer-changed')
        self.assertEqual(pub.digest(current/'dispatcharr-db',True),hashes['dispatcharr-db'])

    def test_copy_owned_rejects_changed_source_without_claiming_success(self):
        source=self.root/'file';source.write_bytes(b'original');source.chmod(0o600)
        shape=helper.content_shape(source)
        with patch.object(helper,'content_shape',side_effect=[shape,{'changed':('file',1,'x')}]), \
             patch.object(helper.os,'chown'),self.assertRaises(ValueError):
            helper.copy_owned(source,self.root/'target',0,0)

    def test_old_teamarr_fixture_closes_wal_connection_before_five_surface_staging(self):
        path=self.root/'teamarr-db'
        connection=sqlite3.connect(path)
        try:
            self.assertEqual(connection.execute('PRAGMA journal_mode=WAL').fetchone(),('wal',))
            connection.execute('CREATE TABLE atlas_teamarr_probe(id INTEGER PRIMARY KEY,marker TEXT)')
            connection.execute("INSERT INTO atlas_teamarr_probe VALUES(1,'snapshot')")
            connection.commit()
        finally:connection.close()
        path.chmod(0o600)
        helper.mark_old_teamarr(path)
        self.assertEqual({p.name for p in self.root.iterdir()},{'teamarr-db'})
        connection=sqlite3.connect(path)
        try:
            self.assertEqual(connection.execute('SELECT marker FROM atlas_teamarr_probe').fetchall(),[('old-combined',)])
            self.assertEqual(connection.execute('PRAGMA journal_mode').fetchone(),('delete',))
        finally:connection.close()

    def lifecycle(self,fail_probe=False):
        cleanup=Mock();modes=[];helpers={};stopped={'Status':'exited','Running':False,'Pid':0,'ExitCode':0,'OOMKilled':False}
        def factory(image):
            base=types.SimpleNamespace(IMAGE=image,LABEL=driver.LABEL,DEPLOYMENT='expected',cleanup=cleanup)
            base.container_options=lambda name,identifier:['--name',name,'--network=none']
            def invoke(*args,**kwargs):
                if args[0]=='git':
                    return subprocess.CompletedProcess(args,0,b'' if 'status' in args else driver.HEAD.encode(),b'')
                if args[:2]==('docker','create') and '--entrypoint' in args:
                    helpers[args[args.index('--name')+1]]=args[-2]
                if args[:3]==('docker','start','--attach'):
                    mode=helpers[args[-1]];modes.append(mode)
                    value={'version':1,'scope':'synthetic-combined-sports','mode':mode,'checks_passed':True,
                           'production_state_access':False,'live_restore_enabled':False}
                    return subprocess.CompletedProcess(args,1 if fail_probe and mode=='probe' else 0,json.dumps(value).encode(),b'')
                return subprocess.CompletedProcess(args,0,b'',b'')
            base.invoke=invoke
            base.app_arguments=lambda name,volume,identifier:['docker','create','fixture-app',name]
            base.docker=lambda *args,**kw:('updated' if "print('updated')" in str(args[-1]) else 'marker-valid') if args[0]=='exec' else ''
            base.inspect=lambda name:{'Mounts':[],'Config':{'Labels':{driver.LABEL:'di' if name=='retained-dispatch' else 'ti'}},'State':stopped}
            base.owned_container=Mock(return_value={'State':stopped})
            return base
        dispatch=types.SimpleNamespace(utilities=lambda root:factory('dispatch-image'),observation=lambda base:[('stable',)],
            wait_ready=Mock(),stop=Mock(),marker_code=lambda *a:'marker',exited=Mock())
        team=types.SimpleNamespace(IMAGE='team-image',utilities=lambda root:factory('team-image'),
            wait_ready=Mock(),stop=Mock(),marker_code=lambda *a:'marker',
            app_arguments=lambda base,name,volume,identifier:['docker','create','fixture-app',name])
        def d_run():
            base=dispatch.utilities(ROOT)
            base.cleanup(('retained-dispatch',),'atlas-dispatch-drill-source-di','di')
            base.cleanup((),'atlas-dispatch-drill-target-di','di')
        def t_run():team.utilities(ROOT).cleanup(('retained-team',),'atlas-teamarr-drill-data-ti','ti')
        dispatch.run=d_run;team.run=t_run
        pointer=Mock();pointer.is_file.return_value=True;pointer.is_symlink.return_value=False;pointer.read_bytes.return_value=b'expected'
        real_path=Path
        def paths(value):return pointer if str(value)=='/mnt/storage/configs/atlas/deployments/current' else real_path(value)
        output=io.StringIO();error=io.StringIO()
        with patch.object(driver,'component',side_effect=lambda root,path:dispatch if 'dispatcharr' in path else team), \
             patch.object(driver,'Path',side_effect=paths),patch.object(driver,'pack',return_value=(b'payload','bootstrap')), \
             patch.object(driver,'attest',return_value={'State':stopped}), \
             contextlib.redirect_stdout(output),contextlib.redirect_stderr(error):
            if fail_probe:
                with self.assertRaises(RuntimeError):driver.run()
            else:driver.run()
        return modes,cleanup,output.getvalue(),dispatch,team

    def test_combined_lifecycle_restarts_both_consumers_before_joint_undo_and_cleanup(self):
        modes,cleanup,output,dispatch,team=self.lifecycle()
        self.assertEqual(modes,['collect','stage','materialize','probe','probe','verify-consumers','rollback'])
        self.assertEqual(dispatch.wait_ready.call_count,2);self.assertEqual(team.wait_ready.call_count,2)
        self.assertEqual(dispatch.stop.call_count,2);self.assertEqual(team.stop.call_count,2)
        self.assertEqual(cleanup.call_count,7)
        # Exited combined helpers still hold component input volumes. They must
        # be removed before the component's volume-removal calls.
        calls=cleanup.call_args_list
        self.assertTrue(calls[0].args[1].startswith('atlas-combined-journal-'))
        self.assertTrue(any(n.startswith('atlas-combined-helper-') for n in calls[0].args[0]))
        self.assertEqual([c.args[1] for c in calls[-3:]],['atlas-dispatch-drill-source-di','atlas-dispatch-drill-target-di','atlas-teamarr-drill-data-ti'])
        self.assertIn('SYNTHETIC_COMBINED_SPORTS_RECOVERY_DRILL=PASS',output)

    def test_failed_consumer_probe_attempts_journal_undo_and_cleans_all_volumes_without_pass(self):
        modes,cleanup,output,dispatch,team=self.lifecycle(fail_probe=True)
        self.assertEqual(modes,['collect','stage','materialize','probe','rollback'])
        self.assertEqual(cleanup.call_count,7)
        self.assertNotIn('SYNTHETIC_COMBINED_SPORTS_RECOVERY_DRILL=PASS',output)
        dispatch.wait_ready.assert_not_called();team.wait_ready.assert_not_called()

    def test_payload_pins_and_component_sources_are_reviewed(self):
        data,bootstrap=driver.pack(ROOT);compile(bootstrap,'<bootstrap>','exec')
        self.assertEqual(set(json.loads(data)),set(driver.SUPPORT_HASHES))
        for name in driver.PINS:driver.component(ROOT,name)
        self.assertGreater(len(driver.SUPPORT_HASHES),10)


if __name__=='__main__':unittest.main()
