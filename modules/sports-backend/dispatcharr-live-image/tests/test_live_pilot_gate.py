"""Pilot ingress refuses excluded playback before any view is called."""
import ast, hashlib, importlib.util, os
from pathlib import Path
from types import ModuleType, SimpleNamespace as Row
import sys, tempfile, unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
gate=load('pilot_gate_under_test',ROOT/'apps/m3u/live_pilot_gate.py')
installer=load('pilot_installer_under_test',ROOT/'install_live_pilot.py')
ON={'ATLAS_SPORTS_PILOT_MODE':'live-only','ATLAS_VERIFIED_LIVE_MODE':'strict',
    'ATLAS_RESERVATION_LEDGER_MIGRATED':'1'}

class Response(dict):
    def __init__(self,payload,status):super().__init__();self.status_code=status;self.payload=payload

class PilotGateTests(unittest.TestCase):
    def setUp(self):
        self.environment=patch.dict(os.environ,{},clear=True);self.environment.start()
        http=ModuleType('django.http');http.JsonResponse=Response
        self.django=patch.dict(sys.modules,{'django':ModuleType('django'),'django.http':http});self.django.start()
    def tearDown(self):self.django.stop();self.environment.stop()
    def enabled(self):os.environ.update(ON)
    def test_default_off_keeps_existing_behavior(self):
        downstream=Mock(return_value='existing');middleware=gate.LiveSportsPilotMiddleware(downstream)
        self.assertEqual(middleware(Row(path_info='/movie/a/b/1.ts')),'existing')
        view=Mock(return_value='legacy');wrapped=gate.wrap_live_view(view,network_allowed=Mock(),
            get_object=Mock(),channel_type=Row,server_factory=Mock())
        self.assertEqual(wrapped(Row(method='GET'),'channel'),'legacy')
    def test_excluded_paths_refuse_before_view_for_all_methods(self):
        self.enabled();downstream=Mock(side_effect=AssertionError('view must not run'))
        middleware=gate.LiveSportsPilotMiddleware(downstream)
        paths=('/movie/user/password/1.ts','/series/u/p/1.mkv','/timeshift/u/p/60/date/1.ts',
            '/streaming/timeshift.php','/streaming/timeshift.php/','/proxy/vod/movie/id/session',
            '/proxy/catchup/channel','/api/vod','/api/vod/movies/','/api/catchup/sessions/',
            '/proxy/hls/stream/channel')
        for path in paths:
            for method in ('GET','HEAD','POST','OPTIONS'):
                response=middleware(Row(path_info=path,method=method))
                self.assertEqual(response.status_code,503);self.assertEqual(response['Cache-Control'],'no-store')
        downstream.assert_not_called()
    def test_alias_callbacks_are_refused(self):
        self.enabled();middleware=gate.LiveSportsPilotMiddleware(Mock())
        for module in ('apps.proxy.vod_proxy.views','apps.timeshift.views','apps.timeshift.api_views','apps.proxy.hls_proxy.views'):
            callback=Mock();callback.__module__=module
            self.assertEqual(middleware.process_view(Row(),callback,(),{}).status_code,503)
    def test_invalid_or_partial_activation_fails_closed(self):
        for variable,value in [('ATLAS_SPORTS_PILOT_MODE','typo'),('ATLAS_VERIFIED_LIVE_MODE','off'),
                               ('ATLAS_RESERVATION_LEDGER_MIGRATED','0')]:
            os.environ.update(ON);os.environ[variable]=value
            downstream=Mock();response=gate.LiveSportsPilotMiddleware(downstream)(Row(path_info='/'))
            self.assertEqual(response.status_code,503);downstream.assert_not_called()
    def wrapped(self,obj=None,server=None,network=None):
        view=Mock(return_value='original');lookup=Mock(return_value=obj)
        factory=Mock(return_value=server)
        wrapped=gate.wrap_live_view(view,network_allowed=network or Mock(return_value=True),
            get_object=lookup,channel_type=Row,server_factory=factory)
        return wrapped,view,lookup,factory
    def test_direct_stream_preview_is_refused_before_server(self):
        self.enabled();wrapped,view,lookup,factory=self.wrapped(obj=object())
        self.assertEqual(wrapped(Row(method='GET'),'preview').status_code,503)
        view.assert_not_called();factory.assert_not_called()
    def test_missing_classifier_or_policy_is_refused(self):
        self.enabled()
        for server in (Row(),Row(_managed_channel_classifier=Row(classify=lambda _:True))):
            wrapped,view,_,_=self.wrapped(obj=Row(),server=server)
            self.assertEqual(wrapped(Row(method='GET'),'channel').status_code,503);view.assert_not_called()
    def test_network_denial_and_head_do_not_add_lookup_or_allocation(self):
        self.enabled()
        for method,allowed in [('GET',False),('HEAD',True),('OPTIONS',True),('POST',True)]:
            wrapped,view,lookup,factory=self.wrapped(network=Mock(return_value=allowed))
            self.assertEqual(wrapped(Row(method=method),'channel'),'original')
            lookup.assert_not_called();factory.assert_not_called()
    def test_ready_managed_channel_keeps_original_verified_handler(self):
        self.enabled();classifier=Mock();policy=Mock()
        server=Row(_managed_channel_classifier=classifier,_verified_live_policy_builder=policy)
        wrapped,view,_,_=self.wrapped(obj=Row(),server=server)
        self.assertEqual(wrapped(Row(method='GET'),'channel'),'original')
        view.assert_called_once();classifier.classify.assert_not_called();policy.assert_not_called()
    def test_unmanaged_owner_cannot_fall_back_in_pilot(self):
        path=ROOT/'apps/proxy/live_proxy/verified_routing.py'
        node=next(n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='owner_route')
        scope={'pilot_enabled':gate.pilot_enabled,'AtlasManagedClassificationUnavailable':RuntimeError}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'owner_route','exec'),scope)
        classifier=Row(classify=lambda _:False)
        self.assertEqual(scope['owner_route']('id',classifier=classifier,verified_policy=lambda:None),'legacy')
        self.enabled()
        with self.assertRaises(RuntimeError):scope['owner_route']('id',classifier=classifier,verified_policy=lambda:None)
        classifier.classify=lambda _:True
        self.assertEqual(scope['owner_route']('id',classifier=classifier,verified_policy=lambda:None),'verified')
    def test_installer_is_pinned_idempotent_and_rejects_source_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'dispatcharr').mkdir();path=root/'dispatcharr/settings.py'
            raw=b'MIDDLEWARE = ["existing.SecurityMiddleware"]\nSECRET_VALUE="fixture"\n'
            path.write_bytes(raw)
            with patch.object(installer,'SETTINGS_SHA256',hashlib.sha256(raw).hexdigest()):
                installer.install(root);installed=path.read_bytes();installer.install(root)
                self.assertEqual(path.read_bytes(),installed)
                self.assertEqual(installed.replace(installer.STATEMENT.encode(),b'',1),raw)
                path.write_bytes(installed+b'# unrelated drift\n')
                with self.assertRaises(AssertionError):installer.install(root)
    def test_live_wrapper_is_installed_after_definitions_without_changing_get_body(self):
        tree=ast.parse((ROOT/'apps/proxy/live_proxy/views.py').read_bytes())
        assignments=[n for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='stream_ts' for t in n.targets)]
        self.assertEqual(len(assignments),1)
        self.assertEqual(ast.unparse(assignments[0].value.func),'wrap_live_view')
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='stream_ts')
        self.assertLess(function.lineno,assignments[0].lineno)
    def test_exported_root_playback_aliases_resolve_to_excluded_packages(self):
        tree=ast.parse((ROOT/'tests/fixtures/pilot_root_urls.py').read_bytes())
        imports={alias.asname or alias.name:node.module for node in tree.body
            if isinstance(node,ast.ImportFrom) for alias in node.names}
        expected={'stream_xc_movie','stream_xc_episode','timeshift_proxy','timeshift_proxy_query'}
        callbacks=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'path','re_path'}:
                if len(node.args)>1 and isinstance(node.args[1],ast.Name) and node.args[1].id in expected:
                    callbacks.add(node.args[1].id)
                    module=imports[node.args[1].id]
                    self.assertTrue(module.startswith(('apps.proxy.vod_proxy.','apps.timeshift.')))
        self.assertEqual(callbacks,expected)
        proxy=(ROOT/'tests/fixtures/pilot_proxy_urls.py').read_text()
        self.assertIn("include('apps.proxy.vod_proxy.urls')",proxy)
        self.assertIn("include('apps.timeshift.urls')",proxy)

if __name__=='__main__':unittest.main()
