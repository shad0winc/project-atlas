"""JWT creation and validation for Atlas authentication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Callable, Mapping

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError as PyJWTInvalidTokenError

from atlas_api.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    UnexpectedTokenTypeError,
)
from atlas_api.auth.models import AuthenticatedUser, TokenClaims, TokenType
from atlas_api.core.settings import AtlasAPISettings


Clock = Callable[[], datetime]


class JWTService:
    """Create and validate signed Atlas JWTs."""

    algorithm = "HS256"

    def __init__(
        self,
        settings: AtlasAPISettings,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._settings = settings
        self._clock = clock or _utc_now

    def create_access_token(self, user: AuthenticatedUser) -> str:
        """Create a short-lived access token."""

        return self._create_token(
            user,
            token_type=TokenType.ACCESS,
            lifetime=timedelta(
                minutes=self._settings.access_token_minutes
            ),
        )

    def create_refresh_token(self, user: AuthenticatedUser) -> str:
        """Create a long-lived refresh token."""

        return self._create_token(
            user,
            token_type=TokenType.REFRESH,
            lifetime=timedelta(
                days=self._settings.refresh_token_days
            ),
        )

    def decode_token(
        self,
        token: str,
        *,
        expected_type: TokenType | None = None,
    ) -> TokenClaims:
        """Validate a JWT and return normalized token claims."""

        if not isinstance(token, str) or not token:
            raise InvalidTokenError("Token cannot be empty.")

        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self.algorithm],
                audience=self._settings.jwt_audience,
                issuer=self._settings.jwt_issuer,
                options={
                    "require": [
                        "sub",
                        "username",
                        "roles",
                        "type",
                        "jti",
                        "iat",
                        "exp",
                        "iss",
                        "aud",
                    ]
                },
            )
        except ExpiredSignatureError as error:
            raise ExpiredTokenError("Token has expired.") from error
        except PyJWTInvalidTokenError as error:
            raise InvalidTokenError("Token is invalid.") from error

        claims = self._claims_from_payload(payload)

        if expected_type is not None and claims.token_type is not expected_type:
            raise UnexpectedTokenTypeError(
                f"Expected a {expected_type.value} token, "
                f"received {claims.token_type.value}."
            )

        return claims

    def _create_token(
        self,
        user: AuthenticatedUser,
        *,
        token_type: TokenType,
        lifetime: timedelta,
    ) -> str:
        issued_at = self._clock().astimezone(timezone.utc)
        expires_at = issued_at + lifetime

        payload: dict[str, Any] = {
            "sub": user.user_id,
            "username": user.username,
            "roles": list(user.roles),
            "type": token_type.value,
            "jti": secrets.token_urlsafe(24),
            "iat": issued_at,
            "exp": expires_at,
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
        }

        return jwt.encode(
            payload,
            self._settings.jwt_secret,
            algorithm=self.algorithm,
        )

    @staticmethod
    def _claims_from_payload(
        payload: Mapping[str, Any],
    ) -> TokenClaims:
        try:
            token_type = TokenType(str(payload["type"]))
            roles_value = payload["roles"]

            if not isinstance(roles_value, list):
                raise TypeError("Token roles must be a list.")

            roles = tuple(str(role) for role in roles_value)

            return TokenClaims(
                subject=str(payload["sub"]),
                username=str(payload["username"]),
                roles=roles,
                token_type=token_type,
                token_id=str(payload["jti"]),
                issued_at=int(payload["iat"]),
                expires_at=int(payload["exp"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidTokenError(
                "Token claims are invalid."
            ) from error


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
