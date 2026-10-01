from __future__ import annotations

from functools import lru_cache
import os

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from atlas.media.jellyfin_auth import build_jellyfin_authorization
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


def _jellyfin_authorization() -> str:
    return build_jellyfin_authorization(
        token=_jellyfin_key(),
    )


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
        gateway = _capabilities().exchange_bootstrap(authorization[len(prefix) :])
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
        claims = _capabilities().authorize_session(
            atlas_playback,
            request_uri=forwarded_uri,
        )
    except PlaybackCapabilityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Playback session is invalid or out of scope.",
        ) from error

    if claims.get("live_identity"):
        from atlas.jellyfin_live_streams import LiveStreamOwnershipError
        from atlas_api.routes.v1.playback import get_playback_service

        try:
            get_playback_service().authorize_live_stream(
                user_id=claims["sub"],
                item_id=claims["item"],
                live_stream_id=claims["live_identity"]["livestreamid"],
                play_session_id=claims["live_identity"]["playsessionid"],
                media_source_id=claims["live_identity"]["mediasourceid"],
            )
        except LiveStreamOwnershipError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Live playback owner is unavailable.",
            ) from exc

    response = Response(status_code=status.HTTP_200_OK)
    response.headers["X-Atlas-Jellyfin-Authorization"] = _jellyfin_authorization()
    response.headers["Cache-Control"] = "no-store"
    return response
