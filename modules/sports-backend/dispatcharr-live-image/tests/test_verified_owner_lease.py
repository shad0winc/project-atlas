"""Exercise the real lease methods through the request-to-initializer handoff."""
import ast
from pathlib import Path
import types
import unittest
import uuid

SOURCE=Path(__file__).resolve().parents[1]/'apps/proxy/live_proxy/server.py'
tree=ast.parse(SOURCE.read_bytes())
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ProxyServer')
NAMES=('try_acquire_ownership','_execute_redis_command','get_channel_owner','am_i_owner')
nodes=[next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name) for name in NAMES]

class Redis:
    """Redis-py SET NX and compare/expire semantics, including owner replacement."""
    def __init__(self):
        self.owner=None;self.set_calls=0;self.renewals=0;self.error=None;self.replace_before_eval=None
    def get(self,key):return self.owner
    def set(self,key,value,**kwargs):
        self.set_calls+=1
        if self.error:raise self.error
        if self.owner is not None:return None
        self.owner=value;return True
    def eval(self,script,count,*args):
        if self.error:raise self.error
        if self.replace_before_eval is not None:self.owner=self.replace_before_eval
        if count==2 and "redis.call('SET'" in script:
            return int(bool(self.set(args[0],args[2],nx=True,ex=args[3])))
        if count!=1 or "redis.call('EXPIRE'" not in script:raise AssertionError('Unexpected fixture Lua')
        self.renewals+=1
        return int(self.owner==args[1])

def fixture(redis=None):
    messages=[]
    logger=types.SimpleNamespace(**{level:(lambda message:messages.append(str(message))) for level in ('info','warning','error')})
    namespace=dict(uuid=uuid,logger=logger,RedisKeys=types.SimpleNamespace(channel_owner=lambda channel:'fixture-owner'),GenerationAuthority=types.SimpleNamespace(_keys=lambda channel:('fixture-grant',)),ConnectionError=ConnectionError,TimeoutError=TimeoutError)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),namespace)
    server=types.SimpleNamespace(redis_client=redis or Redis(),worker_id='fixture-worker',_owner_lease_values={})
    for name in NAMES:setattr(server,name,types.MethodType(namespace[name],server))
    return server,messages

class OwnerLeaseTests(unittest.TestCase):
    def test_request_owner_reenters_initializer_with_same_lease(self):
        server,_=fixture();self.assertTrue(server.try_acquire_ownership('channel'))
        lease=server._owner_lease_values['channel']
        self.assertEqual(server.get_channel_owner('channel'),server.worker_id)
        self.assertTrue(server.am_i_owner('channel'))
        self.assertTrue(server.try_acquire_ownership('channel'))
        self.assertEqual(server._owner_lease_values['channel'],lease)
        self.assertEqual(server.redis_client.set_calls,1)
        self.assertEqual(server.redis_client.renewals,1)

    def test_other_worker_is_refused_without_redis_failure_warning(self):
        server,messages=fixture();server.redis_client.owner='other-worker|lease'
        self.assertFalse(server.try_acquire_ownership('channel'))
        self.assertNotIn('channel',server._owner_lease_values)
        self.assertFalse(any('Redis command failed' in message for message in messages))

    def test_expired_known_lease_cannot_be_recreated(self):
        server,_=fixture();server.try_acquire_ownership('channel');server.redis_client.owner=None
        self.assertFalse(server.try_acquire_ownership('channel'))
        self.assertIsNone(server.redis_client.owner);self.assertEqual(server.redis_client.set_calls,1)

    def test_replaced_lease_is_not_renewed_or_overwritten(self):
        server,_=fixture();server.try_acquire_ownership('channel');server.redis_client.owner='new-worker|lease'
        self.assertFalse(server.try_acquire_ownership('channel'))
        self.assertEqual(server.redis_client.owner,'new-worker|lease')
        self.assertEqual(server.redis_client.set_calls,1)

    def test_owner_replacement_between_read_and_renewal_fails_closed(self):
        server,_=fixture();server.try_acquire_ownership('channel');server.redis_client.replace_before_eval='racing-worker|lease'
        self.assertFalse(server.try_acquire_ownership('channel'))
        self.assertEqual(server.redis_client.owner,'racing-worker|lease')

    def test_renewal_error_fails_closed(self):
        server,messages=fixture();server.try_acquire_ownership('channel');server.redis_client.error=ValueError('fixture-error')
        self.assertFalse(server.try_acquire_ownership('channel'))
        self.assertTrue(any('Redis command failed during ownership renewal' in message for message in messages))

    def test_first_acquisition_error_fails_closed(self):
        server,messages=fixture();server.redis_client.error=ValueError('fixture-error')
        self.assertFalse(server.try_acquire_ownership('channel'))
        self.assertNotIn('channel',server._owner_lease_values)
        self.assertTrue(any('Redis command failed during ownership acquisition' in message for message in messages))

    def test_verified_producer_with_lost_owner_is_not_recreated(self):
        server,_=fixture();server.try_acquire_ownership('channel');server.redis_client.owner=None
        calls=[];manager=types.SimpleNamespace(_verified_generation_required=True,renew_verified_generation=lambda:calls.append('failed-generation'))
        server.stream_managers={'channel':manager}
        self.assertFalse(server.try_acquire_ownership('channel'))
        self.assertEqual(calls,['failed-generation']);self.assertIsNone(server.redis_client.owner)

    def test_verified_producer_renews_only_existing_exact_lease(self):
        server,_=fixture();server.try_acquire_ownership('channel')
        manager=types.SimpleNamespace(_verified_generation_required=True,renew_verified_generation=lambda:None)
        server.stream_managers={'channel':manager}
        self.assertTrue(server.try_acquire_ownership('channel'));self.assertEqual(server.redis_client.renewals,1)

    def test_redis_absent_cannot_acquire(self):
        server,_=fixture();server.redis_client=None
        self.assertFalse(server.try_acquire_ownership('channel'))
        self.assertEqual(server._owner_lease_values,{})

if __name__=='__main__':unittest.main()
