"""Artwork is identity-bound, authenticated, bounded, and credential-free."""
import base64
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_api.routes.v1.media_catalog import (
    router, get_media_artwork_service, require_media_catalog_read,
)
from atlas_api.services.media_artwork import (
    MAX_ARTWORK_BYTES, MediaArtwork, MediaArtworkService,
    MediaArtworkError, MediaArtworkNotFound, _NoRedirect,
)

class ImageResponse:
    def __init__(self, body=b'\xff\xd8\xfffixture', media_type='image/jpeg'):
        self.body = body
        self.headers = Message()
        self.headers['Content-Type'] = media_type
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, limit): return self.body[:limit]

@pytest.mark.parametrize('item_id', ['../secret', 'id?api_key=secret', 'https://elsewhere', '', 'a'*129])
def test_invalid_item_never_contacts_provider(item_id):
    with patch('atlas_api.services.media_artwork.build_opener') as opener:
        with pytest.raises(MediaArtworkNotFound):
            MediaArtworkService('http://jellyfin:8096', 'PRIVATE_TOKEN').read_primary(item_id)
        opener.assert_not_called()

@pytest.mark.parametrize('url', ['http://user:password@jellyfin', 'file:///etc/passwd', 'http://jellyfin?token=secret'])
def test_unsafe_provider_configuration_refused(url):
    with pytest.raises(MediaArtworkError):
        MediaArtworkService(url, 'PRIVATE_TOKEN').read_primary('item-1')

def test_exact_identity_get_and_secret_only_in_header():
    with patch('atlas_api.services.media_artwork.build_opener') as opener:
        opener.return_value.open.return_value = ImageResponse()
        image = MediaArtworkService('http://jellyfin:8096/base', 'PRIVATE_TOKEN').read_primary('item-1')
        request = opener.return_value.open.call_args.args[0]
        assert request.full_url == 'http://jellyfin:8096/base/Items/item-1/Images/Primary?maxWidth=240&quality=80'
        assert request.method == 'GET'
        assert 'PRIVATE_TOKEN' not in request.full_url
        assert 'PRIVATE_TOKEN' in request.get_header('Authorization')
        assert image.media_type == 'image/jpeg'
        assert base64.b64decode(image.data_base64) == b'\xff\xd8\xfffixture'
        assert 'PRIVATE_TOKEN' not in image.data_base64

@pytest.mark.parametrize('response', [ImageResponse(b''), ImageResponse(b'x'*(MAX_ARTWORK_BYTES+1)), ImageResponse(b'<svg/>','image/svg+xml'), ImageResponse(b'bad','text/html')])
def test_missing_oversize_or_active_formats_not_returned(response):
    with patch('atlas_api.services.media_artwork.build_opener') as opener:
        opener.return_value.open.return_value = response
        with pytest.raises(MediaArtworkError):
            MediaArtworkService('http://jellyfin', 'PRIVATE_TOKEN').read_primary('item-1')

def test_redirects_refused():
    assert _NoRedirect().redirect_request(None,None,302,'',{},'http://elsewhere') is None

@pytest.mark.parametrize('code,error_type', [(404,MediaArtworkNotFound),(302,MediaArtworkError),(500,MediaArtworkError)])
def test_http_error_details_are_not_exposed(code,error_type):
    with patch('atlas_api.services.media_artwork.build_opener') as opener:
        opener.return_value.open.side_effect = HTTPError('http://private',code,'PRIVATE_TOKEN',{},None)
        with pytest.raises(error_type) as error:
            MediaArtworkService('http://jellyfin', 'PRIVATE_TOKEN').read_primary('item-1')
        assert 'PRIVATE_TOKEN' not in str(error.value)

class FixtureService:
    def read_primary(self,item_id):
        assert item_id == 'item-1'
        return MediaArtwork('image/jpeg','/9j/Zml4dHVyZQ==')

def route_app():
    app = FastAPI();app.include_router(router,prefix='/api/v1')
    app.dependency_overrides[get_media_artwork_service] = FixtureService
    return app

def test_artwork_route_is_protected():
    from atlas_api.main import app
    schema = app.openapi()['paths']['/api/v1/media/catalog/{item_id}/artwork']['get']
    assert schema.get('security')

def test_successful_artwork_response_never_publicly_cached():
    app = route_app()
    app.dependency_overrides[require_media_catalog_read] = lambda: object()
    with TestClient(app) as client:
        response = client.get('/api/v1/media/catalog/item-1/artwork')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.json() == {'media_type':'image/jpeg','data_base64':'/9j/Zml4dHVyZQ=='}

@pytest.mark.parametrize('error,code', [(MediaArtworkNotFound('PRIVATE_TOKEN'),404),(MediaArtworkError('PRIVATE_TOKEN'),503)])
def test_route_failure_is_sanitized(error,code):
    app = route_app();app.dependency_overrides[require_media_catalog_read] = lambda: object()
    class FailingService:
        def read_primary(self,_):raise error
    app.dependency_overrides[get_media_artwork_service] = FailingService
    with TestClient(app) as client:
        response=client.get('/api/v1/media/catalog/item-1/artwork')
    assert response.status_code == code
    assert response.json() == {'detail':'Artwork is unavailable.'}

def test_unauthenticated_user_cannot_read_provider_image(monkeypatch,tmp_path):
    from atlas_api.main import app
    from atlas_api.dependencies import clear_dependency_caches
    monkeypatch.setenv('ATLAS_JWT_SECRET','artwork-test-secret-0123456789abcdef')
    audit=tmp_path/'audit.jsonl';audit.write_text('');audit.chmod(0o660)
    monkeypatch.setenv('ATLAS_SECURITY_AUDIT_PATH',str(audit))
    clear_dependency_caches()
    try:
        with patch('atlas_api.services.media_artwork.build_opener') as opener:
            response=TestClient(app).get('/api/v1/media/catalog/item-1/artwork')
            assert response.status_code == 401
            opener.assert_not_called()
    finally:clear_dependency_caches()
