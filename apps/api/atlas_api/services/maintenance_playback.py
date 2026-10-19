"""Maintenance preview requires both a video capability and a current admin login.

No maintenance cookie crosses origins. The signed video token carries only an
opaque reference to its original Atlas access/refresh session in this API process.
"""
from fastapi import HTTPException, Request

from atlas_api.auth.models import TokenType
from atlas_api.services.maintenance_access import _dependency, global_admin


def issue_maintenance_media_binding(request: Request) -> str | None:
    from atlas_api.dependencies import (
        get_authentication_service, get_jwt_service, get_maintenance_control_client,
    )
    if _dependency(request.app, get_maintenance_control_client) is None:
        return None
    try:
        header = request.headers.get('authorization', '')
        scheme, _, token = header.partition(' ')
        if scheme.lower() != 'bearer' or not token or len(token) > 8192:
            raise ValueError('Missing access session')
        claims = _dependency(request.app, get_jwt_service).decode_token(
            token, expected_type=TokenType.ACCESS)
        authentication = _dependency(request.app, get_authentication_service)
        if not authentication.maintenance_access_active(claims):
            raise ValueError('Inactive access session')
        return authentication.maintenance_media_binding(claims)
    except Exception:
        raise HTTPException(401, 'An active Atlas login is required for playback.') from None


def request_media_admin(app, request) -> bool:
    from atlas_api.dependencies import get_authentication_service, get_user_profile_store
    from atlas_api.routes.playback_gateway import _capabilities

    try:
        capabilities = _capabilities()
        if request.method == 'POST' and request.url.path == '/_atlas/playback/bootstrap':
            scheme, _, token = request.headers.get('authorization', '').partition(' ')
            if scheme.lower() != 'bearer' or not token or len(token) > 8192:
                return False
            claims = capabilities.inspect_bootstrap(token)
        elif request.method == 'GET' and request.url.path == '/_atlas/playback/authorize':
            token = request.cookies.get('atlas_playback', '')
            uri = request.headers.get('x-forwarded-uri', '').strip()
            if not token or len(token) > 8192 or not uri or len(uri) > 16384:
                return False
            claims = capabilities.authorize_session(token, request_uri=uri)
        else:
            return False
        reference = claims.get('maintenance_binding')
        if not isinstance(reference, str) or len(reference) != 64:
            return False
        authentication = _dependency(app, get_authentication_service)
        subject = authentication.maintenance_media_subject(reference)
        if subject is None or subject != claims['sub']:
            return False
        return global_admin(_dependency(app, get_user_profile_store).get_user(subject))
    except Exception:
        return False
