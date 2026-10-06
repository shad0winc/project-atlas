import pytest
from test_sports_live_playback_route import build_harness, _FakeResourceLease
from atlas_api.services.playback import PlaybackNotFoundError, PlaybackUnavailableError

@pytest.mark.parametrize('error', [PlaybackNotFoundError('missing'), PlaybackUnavailableError('unknown'), RuntimeError('lost response')])
def test_shared_open_failure_keeps_session_and_capacity_for_reconciliation(error):
    harness = build_harness()
    original = harness.resource_pool.acquire
    def acquire(**kwargs):
        lease = original(**kwargs)
        lease.sharing_fingerprint = 'a' * 64
        return lease
    harness.resource_pool.acquire = acquire
    def fail(**kwargs): raise error
    harness.playback.resolve_live_session = fail
    response = harness.client.get('/api/v1/sports/live/sports-event-001/session')
    assert response.status_code == 503
    assert response.json()['detail'] == 'Shared live playback requires cleanup reconciliation.'
    assert harness.resource_pool.release_calls == []
    assert harness.live_sessions.release_calls == []
