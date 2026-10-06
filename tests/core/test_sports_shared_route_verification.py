import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from atlas.sports_shared_admission import SharedAdmissionRoute, SharedAdmissionConfig

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'modules/sports/src'))
import shared_admission as verifier
from live_sources import LiveSource, verify_playback_option, LiveSourceCatalogError
from dispatcharr_admin import DispatcharrAdminClient

class NativeVerificationTests(unittest.TestCase):
    def setUp(self):
        self.route=SharedAdmissionRoute('sports-live-game','account','a'*32,44,'d2818d71-b8c7-42b0-8db5-741bea4f6808',163,2,1,('one','two'),'canary-1')
        self.source=LiveSource('game','Public fixture','http://fixture/proxy/ts/stream/'+self.route.dispatcharr_channel_uuid,resource_source_ids=('account',))
        self.resource=SimpleNamespace(source_id='account',backend_reference='dispatcharr:m3u:2',max_connections=1,enabled=True)
        self.native_channel={'id':44,'uuid':self.route.dispatcharr_channel_uuid,'name':'Fixture','streams':[163]}
        self.native_stream={'id':163,'m3u_account':2,'is_stale':False}
        self.account=SimpleNamespace(account_id=2,enabled=True,credentials_configured=True,configured_max_connections=1)
        test=self
        class Client:
            _base_url='http://fixture'
            _safe_channel=staticmethod(DispatcharrAdminClient._safe_channel)
            def _access_token(self): return 'fixture'
            def _json_request(self,method,path,**kwargs):
                assert method=='GET'
                return test.native_channel if '/channels/channels/' in path else test.native_stream
            def read_account(self,account_id):
                assert account_id==2
                return test.account
        self.client=Client()
        self.binding=SimpleNamespace(dispatcharr_channel_id=44,dispatcharr_channel_uuid=self.route.dispatcharr_channel_uuid)
        self.jellyfin_item='a'*32
    def verify(self):
        binding=self.binding
        with patch.object(verifier,'load_shared_admission',return_value=SharedAdmissionConfig((self.route,))), \
             patch.object(verifier,'default_live_source_registry',return_value=SimpleNamespace(list_sources=lambda:[self.source])), \
             patch.object(verifier,'default_dispatcharr_channel_binding_registry',return_value=SimpleNamespace(resolve=lambda _:binding)), \
             patch.object(verifier,'default_live_tv_binding_registry',return_value=SimpleNamespace(resolve=lambda _:self.jellyfin_item)), \
             patch.object(verifier,'verify_configured_playback_option',side_effect=lambda source,option,resources:verify_playback_option(source,option,resources,self.client)):
            return verifier.verify_shared_live_route(self.route.target_id,[self.resource])
    def test_matching_native_route_returns_only_exact_receipt(self):
        self.assertEqual(self.verify(),{'target_id':self.route.target_id,'fingerprint':self.route.fingerprint})
        self.assertEqual(self.source.playback_options,())
    def test_native_changes_and_stale_feed_block_receipt(self):
        for field,value in [('m3u_account',3),('is_stale',True),('id',164)]:
            self.native_stream={'id':163,'m3u_account':2,'is_stale':False};self.native_stream[field]=value
            with self.subTest(field=field),self.assertRaises(LiveSourceCatalogError): self.verify()
        self.native_stream={'id':163,'m3u_account':2,'is_stale':False}
        self.native_channel['streams']=[163,164]
        with self.assertRaises(LiveSourceCatalogError): self.verify()
    def test_disabled_account_or_changed_resource_capacity_blocks_receipt(self):
        self.account.enabled=False
        with self.assertRaises(LiveSourceCatalogError): self.verify()
        self.account.enabled=True;self.resource.max_connections=2
        with self.assertRaises(LiveSourceCatalogError): self.verify()
    def test_changed_publication_bindings_block_receipt(self):
        self.binding.dispatcharr_channel_id=45
        with self.assertRaises(LiveSourceCatalogError): self.verify()
        self.binding.dispatcharr_channel_id=44; self.jellyfin_item='b'*32
        with self.assertRaises(LiveSourceCatalogError): self.verify()
    def test_changed_actual_account_mapping_and_url_block_receipt(self):
        self.resource.backend_reference='dispatcharr:m3u:3'
        with self.assertRaises(LiveSourceCatalogError): self.verify()
        self.resource.backend_reference='dispatcharr:m3u:2'
        from dataclasses import replace
        self.source=replace(self.source,stream_url='http://fixture/other')
        with self.assertRaises(LiveSourceCatalogError): self.verify()

if __name__=='__main__': unittest.main()
