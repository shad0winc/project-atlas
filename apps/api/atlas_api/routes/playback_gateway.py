from __future__ import annotations

from functools import lru_cache
import os

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from atlas_api.dependencies import get_settings
from atlas_api.playback_capabilities import (
    PlaybackCapabilityError,
    PlaybackCapabilityService,
)

router = APIRouter(prefix="/_atlas/playback", tags=["playback-gateway"])
_COOKIE_NAME = "atlas_playback"


@lru_cache(maxsize=1)
def _capabilities() -> PlaybackCapabilityService:
    return PlaybackCapabilityService(get_settings())


def _jellyfin_key() -> str:
    value = os.getenv("ATLAS_JELLYFIN_API_KEY", "").strip()
    if not value:
        raise RuntimeError("ATLAS_JELLYFIN_API_KEY is required.")
    return value


@router.post("/bootstrap")
def bootstrap_playback(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> JSONResponse:
    prefix = "Bearer "
    if authorization is None or not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Playback capability is required.",
        )
    try:
        gateway = _capabilities().exchange_bootstrap(authorization[len(prefix):])
    except PlaybackCapabilityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Playback capability is invalid or expired.",
        ) from error

    response = JSONResponse(
        {"stream_url": "https://playback.shadowinc.co" + gateway.stream_path}
    )
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        key=_COOKIE_NAME,
        value=gateway.token,
        max_age=gateway.max_age_seconds,
        secure=True,
        httponly=True,
        samesite="lax",
        path=gateway.path_prefix,
    )
    return response


@router.get("/authorize")
def authorize_playback(
    request: Request,
    atlas_playback: str | None = Cookie(default=None, alias=_COOKIE_NAME),
) -> Response:
    if atlas_playback is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Playback session is required.",
        )
    forwarded_uri = request.headers.get("X-Forwarded-Uri", "").strip()
    if not forwarded_uri:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Playback request scope is required.",
        )
    try:
        _capabilities().authorize_session(
            atlas_playback,
            request_uri=forwarded_uri,
        )
    except PlaybackCapabilityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Playback session is invalid or out of scope.",
        ) from error

    response = Response(status_code=status.HTTP_200_OK)
    response.headers["X-Atlas-Jellyfin-Token"] = _jellyfin_key()
    response.headers["Cache-Control"] = "no-store"
    return response
