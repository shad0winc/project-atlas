from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any
from urllib.parse import urlsplit

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from atlas_api.core.settings import AtlasAPISettings


class PlaybackCapabilityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlaybackGatewaySession:
    token: str
    stream_path: str
    path_prefix: str
    max_age_seconds: int


class PlaybackCapabilityService:
    algorithm = "HS256"
    bootstrap_audience = "atlas-playback-bootstrap"
    session_audience = "atlas-playback-session"
    bootstrap_seconds = 120
    session_seconds = 6 * 60 * 60

    def __init__(self, settings: AtlasAPISettings) -> None:
        self._settings = settings

    def create_bootstrap(
        self,
        *,
        user_id: str,
        playable_target_id: str,
        stream_path: str,
    ) -> str:
        normalized_user = self._required(user_id, "user_id")
        normalized_item = self._required(playable_target_id, "playable_target_id")
        normalized_stream, path_prefix = self._stream_scope(stream_path)
        return self._encode(
            audience=self.bootstrap_audience,
            lifetime_seconds=self.bootstrap_seconds,
            payload={
                "kind": "playback_bootstrap",
                "sub": normalized_user,
                "item": normalized_item,
                "stream": normalized_stream,
                "scope": path_prefix,
            },
        )

    def exchange_bootstrap(self, token: str) -> PlaybackGatewaySession:
        payload = self._decode(
            token,
            audience=self.bootstrap_audience,
            expected_kind="playback_bootstrap",
        )
        user_id = self._required(str(payload["sub"]), "sub")
        playable_target_id = self._required(str(payload["item"]), "item")
        stream_path, path_prefix = self._stream_scope(str(payload["stream"]))
        if str(payload.get("scope") or "") != path_prefix:
            raise PlaybackCapabilityError("Playback capability scope is invalid.")

        session_token = self._encode(
            audience=self.session_audience,
            lifetime_seconds=self.session_seconds,
            payload={
                "kind": "playback_session",
                "sub": user_id,
                "item": playable_target_id,
                "scope": path_prefix,
            },
        )
        return PlaybackGatewaySession(
            token=session_token,
            stream_path=stream_path,
            path_prefix=path_prefix,
            max_age_seconds=self.session_seconds,
        )

    def authorize_session(self, token: str, *, request_uri: str) -> None:
        payload = self._decode(
            token,
            audience=self.session_audience,
            expected_kind="playback_session",
        )
        scope = str(payload.get("scope") or "")
        if not scope.startswith("/videos/") or not scope.endswith("/"):
            raise PlaybackCapabilityError("Playback session scope is invalid.")
        if not urlsplit(request_uri).path.startswith(scope):
            raise PlaybackCapabilityError(
                "Playback request is outside the authorized scope."
            )

    def _encode(
        self,
        *,
        audience: str,
        lifetime_seconds: int,
        payload: dict[str, Any],
    ) -> str:
        now = datetime.now(timezone.utc)
        claims = {
            **payload,
            "jti": secrets.token_urlsafe(24),
            "iat": now,
            "exp": now + timedelta(seconds=lifetime_seconds),
            "iss": self._settings.jwt_issuer,
            "aud": audience,
        }
        return jwt.encode(
            claims,
            self._settings.jwt_secret,
            algorithm=self.algorithm,
        )

    def _decode(
        self,
        token: str,
        *,
        audience: str,
        expected_kind: str,
    ) -> dict[str, Any]:
        if not isinstance(token, str) or not token.strip():
            raise PlaybackCapabilityError("Playback capability is required.")
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self.algorithm],
                audience=audience,
                issuer=self._settings.jwt_issuer,
                options={
                    "require": [
                        "sub",
                        "kind",
                        "jti",
                        "iat",
                        "exp",
                        "iss",
                        "aud",
                    ]
                },
            )
        except ExpiredSignatureError as error:
            raise PlaybackCapabilityError(
                "Playback capability has expired."
            ) from error
        except InvalidTokenError as error:
            raise PlaybackCapabilityError(
                "Playback capability is invalid."
            ) from error
        if payload.get("kind") != expected_kind:
            raise PlaybackCapabilityError("Playback capability type is invalid.")
        return payload

    @staticmethod
    def _required(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise PlaybackCapabilityError(f"{name} is required.")
        return normalized

    @staticmethod
    def _stream_scope(value: str) -> tuple[str, str]:
        normalized = value.strip()
        if not normalized:
            raise PlaybackCapabilityError("Playback stream path is required.")
        parsed = urlsplit(normalized)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise PlaybackCapabilityError(
                "Playback stream path must be relative to Atlas playback."
            )
        components = [part for part in parsed.path.split("/") if part]
        if len(components) < 3 or components[0].lower() != "videos":
            raise PlaybackCapabilityError(
                "Playback stream path is outside the video namespace."
            )
        lowered_query = parsed.query.lower()
        for marker in ("apikey=", "api_key=", "token=", "x-emby-token="):
            if marker in lowered_query:
                raise PlaybackCapabilityError(
                    "Playback stream path contains authentication material."
                )
        return normalized, f"/videos/{components[1]}/"
