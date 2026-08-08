"""Core authentication service for the Atlas API."""

from __future__ import annotations

from atlas_api.auth.exceptions import InvalidCredentialsError
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import (
    AuthenticatedUser,
    TokenPair,
    TokenType,
)
from atlas_api.auth.provider import AuthenticationProvider
from atlas_api.auth.sessions import RefreshSessionRegistry


class AuthenticationService:
    """Coordinate authentication providers and token issuance."""

    def __init__(
        self,
        provider: AuthenticationProvider,
        jwt_service: JWTService,
        refresh_sessions: RefreshSessionRegistry | None = None,
    ) -> None:
        self._provider = provider
        self._jwt_service = jwt_service
        self._refresh_sessions = (
            refresh_sessions
            if refresh_sessions is not None
            else RefreshSessionRegistry()
        )

    def login(self, username: str, password: str) -> TokenPair:
        """Authenticate credentials and issue an Atlas token pair."""

        normalized_username = username.strip()

        if not normalized_username or not password:
            raise InvalidCredentialsError(
                "Username and password are required."
            )

        user = self._provider.authenticate(
            normalized_username,
            password,
        )

        if user is None:
            raise InvalidCredentialsError(
                "Username or password is incorrect."
            )

        return self._issue_token_pair(user)

    def refresh(
        self,
        refresh_token: str,
        user: AuthenticatedUser,
    ) -> TokenPair:
        """Validate a refresh token and issue a replacement token pair."""

        claims = self._jwt_service.decode_token(
            refresh_token,
            expected_type=TokenType.REFRESH,
        )

        if claims.subject != user.user_id:
            raise InvalidCredentialsError(
                "Refresh token does not belong to this user."
            )

        if not self._refresh_sessions.consume(claims):
            raise InvalidCredentialsError(
                "Refresh token is no longer active."
            )

        return self._issue_token_pair(user)

    def logout(
        self,
        refresh_token: str,
        user: AuthenticatedUser,
    ) -> None:
        """Revoke a structurally valid refresh session if active."""

        claims = self._jwt_service.decode_token(
            refresh_token,
            expected_type=TokenType.REFRESH,
        )

        if claims.subject != user.user_id:
            raise InvalidCredentialsError(
                "Refresh token does not belong to this user."
            )

        self._refresh_sessions.revoke(claims)

    def _issue_token_pair(
        self,
        user: AuthenticatedUser,
    ) -> TokenPair:
        access_token = self._jwt_service.create_access_token(user)
        refresh_token = self._jwt_service.create_refresh_token(user)
        refresh_claims = self._jwt_service.decode_token(
            refresh_token,
            expected_type=TokenType.REFRESH,
        )

        self._refresh_sessions.register(refresh_claims)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
        )
