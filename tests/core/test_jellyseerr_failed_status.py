from unittest.mock import patch
import pytest
from atlas.media_requests import JellyseerrMediaRequestProvider,MediaRequest,MediaRequestStatus

@pytest.mark.parametrize('media_status',[6,7])
@pytest.mark.parametrize('request_status',[2,5])
def test_failed_provider_status_is_a_valid_terminal_result(media_status,request_status):
    resource={'id':4,'type':'movie','status':request_status,'createdAt':'2026-09-05T13:41:33Z','updatedAt':'2026-09-05T17:00:04Z','media':{'tmdbId':1612018,'mediaType':'movie','status':media_status}}
    provider=JellyseerrMediaRequestProvider(base_url='http://fixture.invalid',api_key='fixture')
    with patch.object(JellyseerrMediaRequestProvider,'_get_json',return_value=resource):result=provider.get_status('4')
    assert result.status is MediaRequestStatus.FAILED
    assert result.terminal and result.error and result.available_at is None
    assert 'fixture' not in result.error

@pytest.mark.parametrize('media_status',[1,2,3,4,5])
def test_nonfailed_status_has_no_failure_error(media_status):
    resource={'id':4,'type':'movie','status':2,'updatedAt':'2026-09-05T17:00:04Z','media':{'tmdbId':1612018,'mediaType':'movie','status':media_status}}
    provider=JellyseerrMediaRequestProvider(base_url='http://fixture.invalid',api_key='fixture')
    with patch.object(JellyseerrMediaRequestProvider,'_get_json',return_value=resource):result=provider.get_status('4')
    assert result.error is None

@pytest.mark.parametrize('media_status',[6,7])
def test_recovery_status_preserves_exact_identity_for_failed_media(media_status):
    request=MediaRequest(request_id='fixture-request',user_id='fixture-user',provider='jellyseerr',provider_media_id='1612018',title='Fixture',media_type='movie',audio_preference='english_preferred')
    provider=JellyseerrMediaRequestProvider(base_url='http://fixture.invalid',api_key='fixture',movie_server_id=0,audio_profile_ids={('movie','english_preferred'):7})
    resource={'id':4,'type':'movie','is4k':False,'serverId':0,'profileId':7,'seasons':[],'status':5,'updatedAt':'2026-09-05T17:00:04Z','media':{'tmdbId':1612018,'mediaType':'movie','status':media_status}}
    with patch.object(JellyseerrMediaRequestProvider,'_recovery_json',return_value=resource):result=provider.get_recovery_status(request,4)
    assert result.status is MediaRequestStatus.FAILED and result.error and result.terminal


def test_failed_resource_cannot_bypass_recovery_identity_checks():
    request=MediaRequest(request_id='fixture-request',user_id='fixture-user',provider='jellyseerr',provider_media_id='1612018',title='Fixture',media_type='movie',audio_preference='english_preferred')
    provider=JellyseerrMediaRequestProvider(base_url='http://fixture.invalid',api_key='fixture',movie_server_id=0,audio_profile_ids={('movie','english_preferred'):7})
    resource={'id':4,'type':'movie','is4k':False,'serverId':0,'profileId':7,'seasons':[],'status':5,'updatedAt':'2026-09-05T17:00:04Z','media':{'tmdbId':999,'mediaType':'movie','status':7}}
    from atlas.media_requests import MediaRequestProviderError
    with patch.object(JellyseerrMediaRequestProvider,'_recovery_json',return_value=resource):
        with pytest.raises(MediaRequestProviderError):provider.get_recovery_status(request,4)


def test_reconcile_persists_deleted_request_and_continues_other_requests(tmp_path):
    from atlas.media_requests import JsonMediaRequestRepository,MediaRequestService
    from atlas.media_requests.reconciler import reconcile_active_requests
    repository=JsonMediaRequestRepository(tmp_path/'requests');repository.initialize()
    repository.save(MediaRequest(request_id='deleted',user_id='fixture-user',provider='jellyseerr',provider_media_id='1612018',title='Deleted fixture',media_type='movie',status='processing',provider_request_id='4',created_at='2026-09-05T13:41:33Z',updated_at='2026-09-05T17:00:04Z'))
    repository.save(MediaRequest(request_id='active',user_id='fixture-user',provider='jellyseerr',provider_media_id='969681',title='Active fixture',media_type='movie',status='approved',provider_request_id='11',created_at='2026-09-05T13:41:33Z'))
    provider=JellyseerrMediaRequestProvider(base_url='http://fixture.invalid',api_key='fixture')
    def response(path):
        deleted=path.endswith('/4')
        return {'id':4 if deleted else 11,'type':'movie','status':5 if deleted else 2,'updatedAt':'2026-09-05T17:00:04Z','media':{'tmdbId':1612018 if deleted else 969681,'mediaType':'movie','status':7 if deleted else 3}}
    service=MediaRequestService(repository,(provider,))
    with patch.object(JellyseerrMediaRequestProvider,'_get_json',side_effect=response):result=reconcile_active_requests(service)
    assert result.failed==0 and result.refreshed==2
    assert repository.get('deleted').status is MediaRequestStatus.FAILED
    assert repository.get('deleted').terminal
    assert repository.get('active').status is MediaRequestStatus.SEARCHING
    with patch.object(JellyseerrMediaRequestProvider,'_get_json',side_effect=response) as transport:
        second=reconcile_active_requests(service)
    assert second.failed==0 and second.skipped==1 and second.refreshed==1
    transport.assert_called_once_with('/api/v1/request/11')
