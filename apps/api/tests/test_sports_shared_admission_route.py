from dataclasses import replace
from types import SimpleNamespace
from apps.api.tests.test_sports_live_playback_route import build_harness, USER
from atlas.sports_shared_admission import SharedAdmissionRoute, SharedAdmissionConfig
from atlas.sports_resource_pool import SportsResourcePool, SportsResourcePoolStateError
from atlas.sports_session_registry import SportsSessionRegistry
from atlas.jellyfin_live_streams import LiveStreamOwnershipError
from atlas_api.routes.v1 import sports_playback
from atlas_api.services.sports import SportsWriterTransportError


def integrated_harness(tmp_path):
    harness=build_harness(); app=harness.client.app
    pin=SharedAdmissionRoute('sports-event-001','primary-account','a'*32,44,
        'd2818d71-b8c7-42b0-8db5-741bea4f6808',163,2,1,(USER.user_id,'viewer-two'),'test-generation')
    config=SharedAdmissionConfig((pin,)); current=[config]
    original_sources=harness.sports.list_live_sources
    def single_source():
        rows=original_sources()
        rows[0]['resource_source_ids']=['primary-account']
        return rows
    harness.sports.list_live_sources=single_source
    pool=SportsResourcePool(tmp_path/'pool.json'); pool.shared_admission_loader=lambda:current[0]
    sessions=SportsSessionRegistry(tmp_path/'sessions.json')
    app.dependency_overrides[sports_playback.get_sports_resource_pool]=lambda:pool
    app.dependency_overrides[sports_playback.get_sports_session_registry]=lambda:sessions
    app.dependency_overrides[sports_playback.get_user_profile_store]=lambda:SimpleNamespace(get_user=lambda user_id:{'jellyfin_user_id':'jf-'+user_id})
    harness.sports.get_live_tv_binding=lambda **kw:{'atlas_channel_id':kw['atlas_channel_id'],'jellyfin_item_id':'a'*32}
    checks=[]
    harness.sports.verify_shared_live_route=lambda **kw:checks.append(kw)
    return harness,pool,current,checks

def viewer(harness,user_id):
    harness.client.app.dependency_overrides[sports_playback.require_sports_read]=lambda:replace(USER,user_id=user_id)

def start(harness): return harness.client.get('/api/v1/sports/live/sports-event-001/session')

def test_two_authenticated_viewers_have_separate_sessions_and_one_allocation(tmp_path):
    harness,pool,current,checks=integrated_harness(tmp_path)
    first=start(harness); assert first.status_code==200
    viewer(harness,'viewer-two'); second=start(harness); assert second.status_code==200
    session_one=first.headers['X-Atlas-Live-Session-ID']; session_two=second.headers['X-Atlas-Live-Session-ID']
    assert session_one!=session_two
    assert len(checks)==2
    snap=pool.snapshot(capacities={'primary-account':1}); assert snap.active==1 and len(snap.leases)==2
    # Owned cleanup of the second viewer frees only that consumer reservation.
    response=harness.client.delete('/api/v1/sports/live/sessions/'+session_two)
    assert response.status_code==204
    snap=pool.snapshot(capacities={'primary-account':1}); assert snap.active==1 and len(snap.leases)==1
    viewer(harness,USER.user_id)
    response=harness.client.delete('/api/v1/sports/live/sessions/'+session_one)
    assert response.status_code==204
    assert pool.snapshot(capacities={'primary-account':1}).active==0

def test_unapproved_viewer_and_native_verification_failure_allocate_nothing(tmp_path):
    harness,pool,current,checks=integrated_harness(tmp_path)
    viewer(harness,'viewer-three'); assert start(harness).status_code==503
    assert checks==[] and not pool.path.exists()
    viewer(harness,USER.user_id)
    def fail(**kw): raise SportsWriterTransportError('native route changed')
    harness.sports.verify_shared_live_route=fail
    assert start(harness).status_code==503
    assert not pool.path.exists()

def test_user_limit_remains_per_viewer_and_revocation_does_not_join(tmp_path):
    harness,pool,current,checks=integrated_harness(tmp_path); harness.policy.limit=1
    assert start(harness).status_code==200
    assert start(harness).status_code==409
    current[0]=SharedAdmissionConfig()
    viewer(harness,'viewer-two'); assert start(harness).status_code==409
    assert len(pool.snapshot(capacities={'primary-account':1}).leases)==1

def test_unknown_cleanup_keeps_reservation_and_bad_config_does_not_block_stop(tmp_path):
    harness,pool,current,checks=integrated_harness(tmp_path)
    response=start(harness); assert response.status_code==200
    session=response.headers['X-Atlas-Live-Session-ID']
    def unavailable(): raise SportsResourcePoolStateError('config changed')
    pool.shared_admission_loader=unavailable
    assert start(harness).status_code==503
    def unknown(**kw): raise LiveStreamOwnershipError('unknown close')
    original=harness.playback.release_live_stream; harness.playback.release_live_stream=unknown
    assert harness.client.delete('/api/v1/sports/live/sessions/'+session).status_code==503
    assert pool.snapshot(capacities={'primary-account':1}).active==1
    # Simulate an independently reconciled close; no automatic retry is invoked.
    harness.playback.release_live_stream=original
    assert harness.client.delete('/api/v1/sports/live/sessions/'+session).status_code==204
    assert pool.snapshot(capacities={'primary-account':1}).active==0
