import os,sys,unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2]/'modules/sports/src'))
from dispatcharr_admin import DispatcharrAdminClient
from live_source_orchestration import reconcile_dispatcharr_channel
class Client(DispatcharrAdminClient):
 def __init__(self):self.calls=[]
 def _access_token(self):return 'fixture'
 def _json_request(self,*args,**kwargs):self.calls.append(args);return args[2]
 def _safe_channel(self,payload):return payload
class Tests(unittest.TestCase):
 def test_create_profile(self):
  c=Client();r=c.create_channel(name='event',stream_ids=[2134],stream_profile_id=3);self.assertEqual(r['stream_profile_id'],3);self.assertEqual(r['streams'],[2134])
 def test_update_preserves_stream_order(self):
  c=Client();r=c.update_channel(channel_id=59,stream_ids=[2192,2134],stream_profile_id=3);self.assertEqual(r,{'streams':[2192,2134],'stream_profile_id':3})
 def test_invalid_profile_before_write(self):
  for profile in (0,-1,True,'3'):
   c=Client()
   with self.assertRaises(Exception):c.create_channel(name='event',stream_ids=[1],stream_profile_id=profile)
   self.assertEqual(c.calls,[])
 def test_missing_deployment_binding_before_any_access(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaises(ValueError):reconcile_dispatcharr_channel(plan=None,dispatcharr=None,bindings=None)
 def test_orchestrator_binds_create_and_update(self):
  from unittest.mock import Mock
  plan=SimpleNamespace(atlas_channel_id='event',name='MNF',stream_ids=(2134,))
  for bound in (None,SimpleNamespace(dispatcharr_channel_id=59)):
   c=Mock();b=Mock();b.resolve.return_value=bound
   native=SimpleNamespace(channel_id=59,channel_uuid='uuid');c.create_channel.return_value=native;c.update_channel.return_value=native
   with patch.dict(os.environ,{'ATLAS_DISPATCHARR_PROXY_PROFILE_ID':'3'}):reconcile_dispatcharr_channel(plan=plan,dispatcharr=c,bindings=b)
   method=c.create_channel if bound is None else c.update_channel
   self.assertEqual(method.call_args.kwargs['stream_profile_id'],3)
if __name__=='__main__':unittest.main()
