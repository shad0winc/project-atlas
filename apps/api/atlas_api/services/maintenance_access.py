"""Server-side maintenance admission for API and ingress forward authorization."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from atlas.maintenance_control import MaintenanceControlError
from atlas.maintenance_control_server import MaintenanceClient
from atlas_api.auth.models import TokenType

COOKIE = '__Host-atlas_maintenance'
AUTH_PATHS = frozenset('/api/v1/auth/' + path for path in (
    'login','refresh','logout','browser/login','browser/refresh','browser/logout'))


def configured_client():
    value = os.getenv('ATLAS_MAINTENANCE_CONTROL_SOCKET')
    if value is None:
        return None  # Source-only compatibility; production deployment must set it.
    path = Path(value)
    if not value.strip() or not path.is_absolute() or str(path) != value:
        raise RuntimeError('Maintenance control configuration is invalid.')
    return MaintenanceClient(path)


def global_admin(profile) -> bool:
    return (isinstance(profile,dict) and profile.get('status') == 'active'
            and isinstance(profile.get('roles'),(list,tuple))
            and any(role in ('admin','global_admin') for role in profile['roles']))


def held(state) -> bool:
    return any(state[key] for key in ('enabled','transition_pending','recovery_held','state_uncertain'))


def control_state(client):
    if client is None:
        raise HTTPException(503,'Maintenance control is not configured.')
    try:
        state = client.request('status')
        if state['state_uncertain']:
            raise HTTPException(503,'Maintenance state is unavailable.')
        return state
    except MaintenanceControlError:
        raise HTTPException(503,'Maintenance control is unavailable.') from None


def admit_authentication(user, client):
    if client is None:
        return
    state = control_state(client)
    if held(state) and not any(role in ('admin','global_admin') for role in user.roles):
        raise HTTPException(503,'Atlas is under maintenance. Administrator access is required.')


def attach_browser_cookie(response, tokens, jwt_service, authentication, profiles):
    if configured_client() is None or authentication is None or profiles is None:
        return
    try:
        claims = jwt_service.decode_token(tokens.refresh_token,expected_type=TokenType.REFRESH)
        profile = profiles.get_user(claims.subject)
        if not global_admin(profile):
            response.delete_cookie(COOKIE,path='/',secure=True,httponly=True,samesite='strict')
            return
        value,lifetime = authentication.maintenance_cookie(tokens.refresh_token)
    except Exception:
        raise HTTPException(503,'Administrator session could not be established.') from None
    response.set_cookie(COOKIE,value,max_age=lifetime,path='/',secure=True,httponly=True,samesite='strict')


def _dependency(app, dependency):
    return app.dependency_overrides.get(dependency,dependency)()


def request_admin(app, request):
    from atlas_api.dependencies import get_authentication_service,get_jwt_service,get_user_profile_store
    try:
        authentication = _dependency(app,get_authentication_service)
        profiles = _dependency(app,get_user_profile_store)
        header = request.headers.get('authorization')
        if header is not None:
            scheme,_,value = header.partition(' ')
            if scheme.lower() != 'bearer' or not value or len(value) > 8192:
                return None
            jwt_service = _dependency(app,get_jwt_service)
            claims = jwt_service.decode_token(value,expected_type=TokenType.ACCESS)
            if not authentication.maintenance_access_active(claims):
                return None
            subject = claims.subject
        else:
            subject = authentication.maintenance_cookie_subject(request.cookies.get(COOKIE,''))
            if subject is None:
                return None
        profile = profiles.get_user(subject)
        return profile if global_admin(profile) else None
    except Exception:
        return None


def install_maintenance_middleware(app):
    from atlas_api.dependencies import get_maintenance_control_client

    @app.middleware('http')
    async def maintenance_boundary(request, call_next):
        # A narrow existing cleanup endpoint still verifies its signed release
        # capability and exact owner/session/target/lease in the route. It grants
        # no browsing or playback, and may drain sessions during an outage.
        if request.method == 'DELETE' and re.fullmatch(
                r'/api/v1/sports/live/sessions/[A-Za-z0-9_-]{1,256}/release-capability', request.url.path):
            return await call_next(request)
        # Deliberately private health exception; public ingress still controls it.
        if request.url.path == '/api/v1/health' and request.method in ('GET','HEAD'):
            return await call_next(request)
        if request.method == 'POST' and request.url.path in (
            '/api/v1/auth/logout','/api/v1/auth/browser/logout'):
            # Revocation must work even if the maintenance authority is down.
            return await call_next(request)
        try:
            client = _dependency(app,get_maintenance_control_client)
            state = await run_in_threadpool(control_state,client) if client is not None else None
        except Exception:
            return JSONResponse({'detail':'Maintenance control is unavailable.'},status_code=503,
                                headers={'Cache-Control':'no-store','Retry-After':'300'})
        internal = request.url.path == '/_atlas/maintenance/authorize'
        closed_origin = request.url.path == '/_atlas/maintenance/closed-origin'
        playback_gate = request.url.path in ('/_atlas/playback/bootstrap','/_atlas/playback/authorize')
        if state is None:
            if internal or closed_origin:
                return JSONResponse({'detail':'Maintenance enforcement is not configured.'},status_code=503)
            return await call_next(request)
        required = (internal or playback_gate) and request.headers.get('x-atlas-maintenance-required') == '1'
        if closed_origin:
            return Response(status_code=503 if held(state) else 204,headers={'Cache-Control':'no-store'})
        if not held(state) and not required:
            if internal:
                return Response(status_code=204,headers={'Cache-Control':'no-store'})
            return await call_next(request)
        if request.method == 'POST' and request.url.path in AUTH_PATHS:
            # Login and refresh have pre-issuance admission; logout always permits revocation.
            return await call_next(request)
        if playback_gate:
            from atlas_api.services.maintenance_playback import request_media_admin
            admitted = await run_in_threadpool(request_media_admin, app, request)
            if admitted:
                return await call_next(request)
            return JSONResponse({'detail':'Maintenance playback requires an active administrator session.'},
                                status_code=503,headers={'Cache-Control':'no-store'})
        profile = await run_in_threadpool(request_admin,app,request)
        if profile is None:
            return JSONResponse({'detail':'Atlas is under maintenance. Administrator access is required.'},
                                status_code=503,headers={'Cache-Control':'no-store','Retry-After':'300'})
        if internal:
            return Response(status_code=204,headers={'Cache-Control':'no-store'})
        return await call_next(request)
