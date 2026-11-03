from pathlib import Path
import ast, os, sys, unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'modules/sports/src'))
import live_source_orchestration as orchestration
from lifecycle import should_surface_game

class WorkerProxyTests(unittest.TestCase):
 def run_worker(self, bound=None, configured=True, resolved=True):
  source=ROOT/'modules/sports/src/worker.py'
  node=next(n for n in ast.parse(source.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='run_live_source_provisioning_pipeline')
  client=Mock();bindings=Mock();registry=Mock()
  bindings.resolve.return_value=bound
  native=SimpleNamespace(channel_id=59,channel_uuid='f7acf454-f042-4f36-9987-9832db74b01f')
  client.create_channel.return_value=native;client.update_channel.return_value=native
  registry.list_sources.return_value=[]
  plan=SimpleNamespace(atlas_channel_id='event',name='MNF',stream_ids=(2134,2192))
  published=object()
  scope={'datetime':datetime,'timezone':timezone,'should_surface_game':should_surface_game,'PREGAME_WINDOW_MINUTES':60,'os':os,
   'resolve_event_live_source_content':Mock(return_value=object() if resolved else None),'build_live_source_provisioning_plan':Mock(return_value=plan),
   'reconcile_dispatcharr_channel':orchestration.reconcile_dispatcharr_channel,'build_published_live_source':Mock(return_value=published),
   'LiveSourceRegistry':object,'DispatcharrChannelBindingRegistry':object,'SportsSource':object,'DispatcharrAdminClient':object}
  import __future__
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec',flags=__future__.annotations.compiler_flag),scope)
  game={'provider':'thesportsdb','provider_event_id':'fixture','status':'live','lifecycle_state':'live'}
  with patch.dict(os.environ,{'ATLAS_DISPATCHARR_PROXY_PROFILE_ID':'3'} if configured else {},clear=True):
   try:
    count=scope['run_live_source_provisioning_pipeline']([game],dispatcharr=client,sources=(object(),),bindings=bindings,live_sources=registry)
   except ValueError:
    if configured:raise
    self.assertFalse(client.create_channel.called);self.assertFalse(client.update_channel.called);self.assertFalse(registry.set.called);return
  if not resolved:
   self.assertEqual(count,0);self.assertFalse(client.create_channel.called);self.assertFalse(client.update_channel.called);self.assertFalse(registry.set.called);return
  self.assertEqual(count,1)
  call=client.update_channel if bound else client.create_channel
  self.assertEqual(call.call_args.kwargs['stream_profile_id'],3)
  self.assertEqual(call.call_args.kwargs['stream_ids'],(2134,2192))
  registry.set.assert_called_once_with(published)
 def test_worker_create_sets_proxy_before_publication(self):self.run_worker()
 def test_worker_existing_channel_sets_proxy(self):self.run_worker(bound=SimpleNamespace(dispatcharr_channel_id=59))
 def test_missing_binding_blocks_writes_and_publication(self):self.run_worker(configured=False)
 def test_unmatched_event_does_not_create_channel(self):self.run_worker(resolved=False)

if __name__=='__main__':unittest.main()
