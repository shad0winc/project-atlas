import importlib.util
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/sports/src'))
sys.path.insert(0, str(ROOT))
from providers.metadata_discovery import discovery_capabilities
from providers.metadata_refresh import RefreshPolicyError
import private_api

spec=importlib.util.spec_from_file_location('discovery_api_service', ROOT / 'apps/api/atlas_api/services/sports.py')
service_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(service_module)


class DiscoveryCapabilitiesTests(unittest.TestCase):
    def capabilities(self, policy=None, directory=''):
        with patch.dict(os.environ, {'ATLAS_SPORTS_METADATA_STATE_DIR':directory}), patch('providers.metadata_refresh.load_refresh_policy',return_value=policy), patch('providers.metadata_service.configured_broker',side_effect=AssertionError('No SQL factory')), patch('providers.metadata_store.MetadataStore',side_effect=AssertionError('No SQL')):
            return discovery_capabilities(True)

    def test_disabled_policy_skips_state_and_keeps_primary_configuration(self):
        result=self.capabilities()
        self.assertEqual(result, {'version':1,'providers':[{'provider':'thesportsdb','enabled':True},{'provider':'espn','enabled':False}]})

    def test_enabled_configuration_is_not_an_effective_health_claim(self):
        result=self.capabilities(SimpleNamespace(), '/not-provisioned/metadata')
        self.assertTrue(result['providers'][1]['enabled'])
        self.assertEqual(set(result), {'version','providers'})
        self.assertNotIn('healthy',json.dumps(result))

    def test_enabled_policy_without_absolute_state_configuration_is_not_advertised(self):
        for directory in ('', 'relative'):
            with self.subTest(directory=directory):
                self.assertFalse(self.capabilities(SimpleNamespace(), directory)['providers'][1]['enabled'])

    def server(self):
        for item in (patch.dict(os.environ,{'ATLAS_SPORTS_WRITER_TOKEN':'test-only'}),patch.object(private_api,'enabled_providers',return_value=[SimpleNamespace(name='thesportsdb')])):
            item.start();self.addCleanup(item.stop)
        server=ThreadingHTTPServer(('127.0.0.1',0),private_api.Handler)
        thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True);thread.start()
        def close():server.shutdown();server.server_close();thread.join(timeout=2)
        self.addCleanup(close)
        return 'http://127.0.0.1:'+str(server.server_port)

    def request(self,url,path,token='test-only'):
        request=urllib.request.Request(url+path,headers={'Authorization':'Bearer '+token})
        try:
            with urllib.request.urlopen(request,timeout=2) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as response:
            with response:return response.code,json.load(response)

    def test_private_auth_precedes_policy_lookup(self):
        url=self.server()
        with patch('providers.metadata_refresh.load_refresh_policy') as load:
            code,_=self.request(url,'/internal/v1/discovery/providers',token='wrong')
            self.assertEqual(code,401);load.assert_not_called()

    def test_unexpected_query_is_rejected_before_policy_lookup(self):
        url=self.server()
        with patch('providers.metadata_refresh.load_refresh_policy') as load:
            code,_=self.request(url,'/internal/v1/discovery/providers?unexpected=1')
            self.assertEqual(code,400);load.assert_not_called()

    def test_private_configuration_response_is_bounded(self):
        url=self.server()
        with patch('providers.metadata_refresh.load_refresh_policy',return_value=None),patch('providers.metadata_service.configured_broker') as factory:
            code,document=self.request(url,'/internal/v1/discovery/providers')
            self.assertEqual(code,200);self.assertEqual(len(document['providers']),2)
            self.assertFalse(document['providers'][1]['enabled']);factory.assert_not_called()

    def test_invalid_policy_is_unavailable_not_disabled_success(self):
        url=self.server()
        with patch('providers.metadata_refresh.load_refresh_policy',side_effect=RefreshPolicyError('Invalid test policy')):
            code,document=self.request(url,'/internal/v1/discovery/providers')
            self.assertEqual(code,503);self.assertNotIn('providers',document)

    def test_api_transport_validates_private_capabilities(self):
        api=service_module.SportsWriterBackedAPIService(base_url='http://writer.test',token='test-only')
        document={'version':1,'providers':[{'provider':'thesportsdb','enabled':True},{'provider':'espn','enabled':False}]}
        with patch.object(api,'_request',return_value=document) as request:
            self.assertEqual(api.discovery_providers(),document)
            request.assert_called_once_with('GET','/internal/v1/discovery/providers')
        for changed in (None,{},dict(document,version=True),dict(document,providers=[]),
                        dict(document,providers=[document['providers'][0]]*2),
                        dict(document,providers=[{'provider':[],'enabled':True},document['providers'][1]]),
                        dict(document,providers=[{'provider':'thesportsdb','enabled':'false'},document['providers'][1]])):
            with self.subTest(document=changed),patch.object(api,'_request',return_value=changed):
                with self.assertRaises(service_module.SportsWriterTransportError):api.discovery_providers()


if __name__=='__main__':unittest.main()
