"""Explicit standalone identity, strict wire validation, and retired history."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as Row
import sys
import tempfile
import unittest
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]

def load(name,relative):
    path=ROOT/relative
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

server=load('standalone_server','modules/sports/src/atlas_live_policy_claim.py')
client=load('standalone_client','modules/sports-backend/dispatcharr-live-image/overlay/apps/m3u/atlas_policy_claims.py')
live_module=load('standalone_live','modules/sports/src/live_sources.py')
binding_module=load('standalone_bindings','modules/sports/src/dispatcharr_channel_bindings.py')

class Response:
    status=200
    def __init__(self,rows):self.raw=json.dumps({'claims':rows}).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,limit):return self.raw[:limit]
class Opener:
    def __init__(self,rows):self.rows=rows
    def open(self,*args,**kwargs):return Response(self.rows)

class StandalonePolicyTests(unittest.TestCase):
    def setUp(self):
        self.uuid=str(uuid4());self.channel='sports-live-nfl-redzone'
        self.binding=Row(atlas_channel_id=self.channel,dispatcharr_channel_uuid=self.uuid)
        self.source=Row(source_id='account-one',enabled=True,backend_reference='dispatcharr:m3u:5',max_connections=1,credential_realm='fixture-realm')
        self.live=Row(atlas_channel_id=self.channel,resource_source_ids=('account-one',),
            stream_url='http://dispatcharr.invalid/proxy/ts/stream/'+self.uuid,
            provider=None,provider_event_id=None,standalone=True)
    def claim(self):
        return server.claim_for_channel(channel_uuid=self.uuid,source_id=self.source.source_id,
            lifecycle_sources=(self.source,),channel_bindings=(self.binding,),live_sources=(self.live,))
    def fetch(self,rows):
        return client.AtlasPolicyClaimClient(origin='http://writer.invalid',token='fixture-policy-token-01234567890123456789',opener=Opener(rows)).fetch(self.uuid)
    def test_standalone_wire_roundtrip_has_no_fabricated_event(self):
        claim=self.claim();wire=claim.to_mapping()
        self.assertEqual(wire['identity_kind'],'standalone');self.assertEqual(wire['standalone_channel_id'],self.channel)
        self.assertNotIn('provider',wire);self.assertNotIn('provider_event_id',wire)
        result,=self.fetch([wire]);self.assertEqual(result.identity_kind,'standalone')
        self.assertIsNone(result.provider);self.assertIsNone(result.provider_event_id)
        self.assertEqual(result.account_id,5)
    def test_event_wire_is_backwards_compatible(self):
        self.live.standalone=False;self.live.provider='fixture';self.live.provider_event_id='game-one'
        wire=self.claim().to_mapping()
        self.assertEqual(set(wire),{'channel_uuid','source_id','account_id','configured_max_connections','credential_realm','provider','provider_event_id'})
        result,=self.fetch([wire]);self.assertEqual(result.identity_kind,'event')
        self.assertEqual(result.provider_event_id,'game-one')
    def test_standalone_still_requires_explicit_realm(self):
        self.source.credential_realm=None
        with self.assertRaisesRegex(server.AtlasLivePolicyUnavailable,'Credential realm'):self.claim()
    def test_standalone_still_requires_current_membership_and_channel_url(self):
        for field,value in [('resource_source_ids',()),('stream_url','http://dispatcharr.invalid/proxy/ts/stream/'+str(uuid4()))]:
            old=getattr(self.live,field);setattr(self.live,field,value)
            try:
                with self.assertRaises(server.AtlasLivePolicyUnavailable):self.claim()
            finally:setattr(self.live,field,old)
    def test_standalone_rejects_ambiguous_event_or_nonboolean_kind(self):
        for field,value in [('provider','fixture'),('provider_event_id','game-one'),('standalone',1)]:
            old=getattr(self.live,field);setattr(self.live,field,value)
            try:
                with self.assertRaises(server.AtlasLivePolicyUnavailable):self.claim()
            finally:setattr(self.live,field,old)
    def test_catalog_does_not_coerce_standalone_strings_or_numbers(self):
        base=dict(id='redzone',name='Fixture',stream_url='http://dispatcharr.invalid/proxy/ts/stream/'+self.uuid,standalone=True)
        self.assertTrue(live_module.normalize_live_source(base).standalone)
        for value in ('false','true',0,1,None):
            with self.subTest(value=value),self.assertRaises(live_module.LiveSourceCatalogError):
                live_module.normalize_live_source(dict(base,standalone=value))
    def test_client_rejects_conflicting_standalone_channel_identities(self):
        row=self.claim().to_mapping();other=dict(row,account_id=6,source_id='account-two',standalone_channel_id='sports-live-other')
        with self.assertRaises(client.AtlasPolicyUnavailable):self.fetch([row,other])
    def test_client_rejects_mixed_event_and_standalone_claims(self):
        row=self.claim().to_mapping();event={k:v for k,v in row.items() if k not in ('identity_kind','standalone_channel_id')}
        event.update(account_id=6,source_id='account-two',provider='fixture',provider_event_id='game-one')
        with self.assertRaises(client.AtlasPolicyUnavailable):self.fetch([row,event])
    def test_client_rejects_invalid_or_extra_standalone_fields(self):
        row=self.claim().to_mapping()
        for changes in ({'identity_kind':'event'},{'standalone_channel_id':'../foreign'},{'provider':'fabricated'},
                        {'configured_max_connections':0},{'credential_realm':''}):
            with self.subTest(changes=changes),self.assertRaises(client.AtlasPolicyUnavailable):self.fetch([dict(row,**changes)])
    def test_retiring_two_copy_channels_preserves_history_and_redzone(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'bindings.json';catalog=root/'live.json'
            ids=('canary-one','canary-two','nfl-redzone');uuids=[str(uuid4()) for _ in ids]
            original={'version':1,'bindings':{'sports-live-'+name:{'dispatcharr_channel_id':i+1,'dispatcharr_channel_uuid':identity}
                for i,(name,identity) in enumerate(zip(ids,uuids))}}
            path.write_text(json.dumps(original))
            catalog.write_text(json.dumps({'version':1,'sources':[dict(id=name,name=name,standalone=True,
                stream_url='http://dispatcharr.invalid/proxy/ts/stream/'+identity) for name,identity in zip(ids,uuids)]}))
            registry=binding_module.DispatcharrChannelBindingRegistry(path);live=live_module.LiveSourceRegistry(catalog)
            registry.migrate_managed_history()
            for name,identity in zip(ids[:2],uuids[:2]):
                self.assertTrue(registry.delete('sports-live-'+name));self.assertTrue(live.delete(name))
                self.assertTrue(registry.managed_history_contains(identity))
                with self.assertRaises(binding_module.DispatcharrChannelBindingError):registry.classify_channel_uuid(identity)
            self.assertTrue(registry.classify_channel_uuid(uuids[2]))
            self.assertEqual(len(json.loads(path.read_bytes())['managed_uuids']),3)
            self.assertEqual([row.source_id for row in live.list_sources()],['nfl-redzone'])

if __name__=='__main__':unittest.main()
