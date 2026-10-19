from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any
from urllib.parse import urlsplit, parse_qsl

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
    release_audience = "atlas-sports-session-release"
    release_seconds = 6 * 60 * 60
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
        maintenance_binding: str | None = None,
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
                **self._maintenance_claim(maintenance_binding),
            },
        )

    def create_live_release(self, *, user_id: str, session_id: str,
                            target_id: str, lease_id: str) -> str:
        return self._encode(
            audience=self.release_audience,
            lifetime_seconds=self.release_seconds,
            payload={"kind": "sports_session_release", "sub": self._required(user_id, "user_id"),
                     "session": self._required(session_id, "session_id"),
                     "target": self._required(target_id, "target_id"),
                     "lease": self._required(lease_id, "lease_id")},
        )

    def authorize_live_release(self, token: str, *, session_id: str) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 4096:
            raise PlaybackCapabilityError("Live release capability is invalid.")
        payload = self._decode(token, audience=self.release_audience,
                               expected_kind="sports_session_release")
        for name in ("sub", "session", "target", "lease"):
            value = payload.get(name)
            if not isinstance(value, str) or not value or len(value) > 256 or value != value.strip():
                raise PlaybackCapabilityError("Live release capability scope is invalid.")
        if payload["session"] != session_id:
            raise PlaybackCapabilityError("Live release capability is out of scope.")
        return payload

    @staticmethod
    def _maintenance_claim(reference: str | None) -> dict[str, str]:
        if reference is None:
            return {}
        if not isinstance(reference, str) or len(reference) != 64 or any(c not in '0123456789abcdef' for c in reference):
            raise PlaybackCapabilityError('Maintenance media binding is invalid.')
        return {'maintenance_binding': reference}

    def inspect_bootstrap(self, token: str) -> dict[str, Any]:
        payload = self._decode(token, audience=self.bootstrap_audience, expected_kind='playback_bootstrap')
        _, scope = self._stream_scope(str(payload.get('stream') or ''))
        if payload.get('scope') != scope:
            raise PlaybackCapabilityError('Playback capability scope is invalid.')
        self._maintenance_claim(payload.get('maintenance_binding'))
        return payload

    def exchange_bootstrap(self, token: str) -> PlaybackGatewaySession:
        payload = self.inspect_bootstrap(token)
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
                "live_identity": self._live_identity(stream_path),
                "entry_path": urlsplit(stream_path).path,
                **self._maintenance_claim(payload.get("maintenance_binding")),
            },
        )
        return PlaybackGatewaySession(
            token=session_token,
            stream_path=stream_path,
            path_prefix=path_prefix,
            max_age_seconds=self.session_seconds,
        )

    def authorize_session(self, token: str, *, request_uri: str) -> dict[str, Any]:
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

        identity = payload.get("live_identity") or {}
        if not identity and any(
            k.lower() == "livestreamid"
            for k, _ in parse_qsl(urlsplit(request_uri).query)
        ):
            raise PlaybackCapabilityError(
                "Live playback identity is outside the authorized scope."
            )
        if identity:
            pairs = parse_qsl(urlsplit(request_uri).query, keep_blank_values=True)
            for name, expected in identity.items():
                supplied = [v for k, v in pairs if k.lower() == name]
                if supplied and supplied != [expected]:
                    raise PlaybackCapabilityError(
                        "Live playback identity is out of scope."
                    )
                if urlsplit(request_uri).path.endswith(".m3u8") and not supplied:
                    raise PlaybackCapabilityError("Live playback identity is required.")
        return payload

    @staticmethod
    def _live_identity(stream_path: str) -> dict[str, str]:
        pairs = parse_qsl(urlsplit(stream_path).query, keep_blank_values=True)
        live = [v for k, v in pairs if k.lower() == "livestreamid"]
        if not live:
            return {}
        result = {}
        for name in ("livestreamid", "mediasourceid", "playsessionid"):
            values = [v for k, v in pairs if k.lower() == name]
            if len(values) != 1 or not values[0]:
                raise PlaybackCapabilityError("Live playback identity is invalid.")
            result[name] = values[0]
        return result

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
            raise PlaybackCapabilityError("Playback capability has expired.") from error
        except InvalidTokenError as error:
            raise PlaybackCapabilityError("Playback capability is invalid.") from error
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
