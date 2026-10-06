import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from atlas.sports_shared_admission import load_shared_admission, SharedAdmissionRoute, SharedAdmissionConfig, verify_api_shared_admission
from atlas.sports_resource_pool import SportsResourcePool, SportsResourcePoolStateError
from atlas.sports_shared_admission_config import SharedAdmissionConfigError

PIN = dict(target_id='sports-live-game', resource_source_id='account', jellyfin_item_id='a'*32,
    dispatcharr_channel_id=44, dispatcharr_channel_uuid='d2818d71-b8c7-42b0-8db5-741bea4f6808',
    dispatcharr_stream_id=163, dispatcharr_account_id=2, capacity=1,
    viewer_user_ids=['one','two'], generation='canary-1')

class AdmissionConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'config.json'
        self.document = dict(version=1, enabled=True, mode='canary', routes=[dict(PIN)])
    def load(self):
        self.path.write_text(json.dumps(self.document)); self.path.chmod(0o600)
        with patch.dict('os.environ', {'ATLAS_SPORTS_SHARED_ADMISSION_FILE': str(self.path)}):
            return load_shared_admission()
    def test_missing_and_disabled_do_not_enable_bindings(self):
        with patch.dict('os.environ', {'ATLAS_SPORTS_SHARED_ADMISSION_FILE': str(self.path)}):
            self.assertEqual(load_shared_admission().bindings(), {})
        self.document['enabled']=False
        self.assertEqual(self.load().bindings(), {})
    def test_invalid_config_never_falls_back_to_shared_or_exclusive(self):
        for field,value in [('capacity',2),('dispatcharr_stream_id',True),('viewer_user_ids',['one','one']),('jellyfin_item_id','invalid')]:
            with self.subTest(field=field):
                self.document['routes']=[dict(PIN,**{field:value})]
                with self.assertRaises(SharedAdmissionConfigError): self.load()
        self.document['routes']=[dict(PIN)]; self.document['mode']='production'
        with self.assertRaises(SharedAdmissionConfigError): self.load()
    def test_duplicate_keys_symlinks_and_writable_config_rejected(self):
        self.path.write_text('{"enabled":false,"enabled":true}'); self.path.chmod(0o600)
        with patch.dict('os.environ', {'ATLAS_SPORTS_SHARED_ADMISSION_FILE': str(self.path)}):
            with self.assertRaises(SharedAdmissionConfigError): load_shared_admission()
        self.load(); self.path.chmod(0o666)
        with patch.dict('os.environ', {'ATLAS_SPORTS_SHARED_ADMISSION_FILE': str(self.path)}):
            with self.assertRaises(SharedAdmissionConfigError): load_shared_admission()
        link=self.path.with_name('link.json'); link.symlink_to(self.path)
        with patch.dict('os.environ', {'ATLAS_SPORTS_SHARED_ADMISSION_FILE': str(link)}):
            with self.assertRaises(SharedAdmissionConfigError): load_shared_admission()
    def test_verified_route_pins_one_resource_and_checks_on_every_admission(self):
        config=self.load(); route=config.routes[0]; calls=[]
        pool=SportsResourcePool(self.path.with_name('pool.json')); pool.shared_admission_loader=lambda:config
        sports=SimpleNamespace(verify_shared_live_route=lambda **kw:calls.append(kw))
        args=dict(target_id=route.target_id, user_id='one', jellyfin_item_id=route.jellyfin_item_id,
            candidates=('backup','account'),capacities={'account':1,'backup':1},configured_options=[])
        for _ in range(2):
            active,candidates=verify_api_shared_admission(pool,sports,**args)
            self.assertEqual(candidates,('account',))
            self.assertEqual(active.sharing_bindings,config.bindings())
        self.assertEqual(len(calls),2)
        for change in ({'user_id':'three'},{'jellyfin_item_id':'b'*32},{'capacities':{'account':2}},{'configured_options':[{}]}):
            with self.subTest(change=change),self.assertRaises(SportsResourcePoolStateError):
                verify_api_shared_admission(pool,sports,**dict(args,**change))
        self.assertEqual(len(calls),2)
    def test_revocation_is_fresh_and_leaves_held_capacity_and_cleanup_available(self):
        config=self.load(); route=config.routes[0]
        pool=SportsResourcePool(self.path.with_name('pool.json')); current=[config]
        pool.shared_admission_loader=lambda:current[0]
        args=dict(target_id=route.target_id,user_id='one',jellyfin_item_id=route.jellyfin_item_id,candidates=('account',),capacities={'account':1},configured_options=[])
        sports=SimpleNamespace(verify_shared_live_route=lambda **kw:None)
        active,_=verify_api_shared_admission(pool,sports,**args)
        lease=active.acquire(user_id='one',target_id=route.target_id,candidate_source_ids=['account'],capacities={'account':1})
        current[0]=SharedAdmissionConfig()
        inactive,_=verify_api_shared_admission(pool,sports,**args)
        self.assertFalse(inactive.sharing_bindings)
        self.assertTrue(pool.release(lease_id=lease.lease_id,user_id='one'))

if __name__=='__main__':unittest.main()
