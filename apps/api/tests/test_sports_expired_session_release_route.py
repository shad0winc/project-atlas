import json
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from atlas.jellyfin_live_streams import LiveStreamOwnershipError
from atlas.sports_resource_pool import SportsResourcePool
from atlas.sports_session_registry import SportsSessionRegistry
from atlas_api.routes.v1.sports_playback import release_sports_live_session


def setup(tmp_path):
    now=[100.0]
    pool=SportsResourcePool(tmp_path/'pool.json',clock=lambda:now[0],sharing_bindings={('game','account'):'a'*64})
    sessions=SportsSessionRegistry(tmp_path/'sessions.json',clock=lambda:now[0])
    def admit(user):
        lease=pool.acquire(user_id=user,target_id='game',candidate_source_ids=('account',),capacities={'account':1},user_limit=1)
        record=sessions.admit(user_id=user,target_id='game',limit=1,resource_lease_id=lease.lease_id)
        return record,lease
    return now,pool,sessions,admit


def test_release_after_expiry_cleans_shared_lease_only_after_stream_cleanup(tmp_path):
    now,pool,sessions,admit=setup(tmp_path)
    record,lease=admit('viewer');now[0]+=1000
    def close(**values):
        assert values=={'session_id':record.session_id,'user_id':'viewer'}
        assert record.session_id in json.loads(sessions.path.read_bytes())['sessions']
        assert lease.lease_id in json.loads(pool.path.read_bytes())['leases']
    response=release_sports_live_session(current_user=SimpleNamespace(user_id='viewer'),live_sessions=sessions,resource_pool=pool,session_id=record.session_id,playback=SimpleNamespace(release_live_stream=close))
    assert response.status_code==204
    assert json.loads(sessions.path.read_bytes())['sessions']=={}
    assert json.loads(pool.path.read_bytes())['leases']=={}


def test_failed_stream_cleanup_preserves_expired_session_and_shared_lease(tmp_path):
    now,pool,sessions,admit=setup(tmp_path)
    record,lease=admit('viewer');now[0]+=1000
    before=(sessions.path.read_bytes(),pool.path.read_bytes())
    def blocked(**values):raise LiveStreamOwnershipError('uncertain closure')
    with pytest.raises(HTTPException) as error:
        release_sports_live_session(current_user=SimpleNamespace(user_id='viewer'),live_sessions=sessions,resource_pool=pool,session_id=record.session_id,playback=SimpleNamespace(release_live_stream=blocked))
    assert error.value.status_code==503
    assert (sessions.path.read_bytes(),pool.path.read_bytes())==before


def test_expired_viewer_release_preserves_second_shared_viewer(tmp_path):
    now,pool,sessions,admit=setup(tmp_path)
    first,first_lease=admit('first');second,second_lease=admit('second')
    now[0]+=1000
    response=release_sports_live_session(current_user=SimpleNamespace(user_id='first'),live_sessions=sessions,resource_pool=pool,session_id=first.session_id,playback=SimpleNamespace(release_live_stream=lambda **values:None))
    assert response.status_code==204
    assert set(json.loads(sessions.path.read_bytes())['sessions'])=={second.session_id}
    assert set(json.loads(pool.path.read_bytes())['leases'])=={second_lease.lease_id}
