"""Core authentication service for the Atlas API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from atlas_api.auth.exceptions import (
    AuthenticationProviderError,
    AuthenticationRateLimitError,
    InvalidCredentialsError,
    TokenError,
)
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import (
    AuthenticatedUser,
    TokenPair,
    TokenType,
)
from atlas_api.auth.provider import AuthenticationProvider
from atlas_api.auth.sessions import RefreshSessionRegistry
from atlas_api.auth.throttling import LoginAttemptLimiter


SecurityAuditPublisher = Callable[[str, Mapping[str, Any]], None]


class AuthenticationService:
    """Coordinate authentication providers, tokens, and security audit."""

    def __init__(
        self,
        provider: AuthenticationProvider,
        jwt_service: JWTService,
        refresh_sessions: RefreshSessionRegistry | None = None,
        login_attempts: LoginAttemptLimiter | None = None,
        audit_publisher: SecurityAuditPublisher | None = None,
    ) -> None:
        self._provider = provider
        self._jwt_service = jwt_service
        self._refresh_sessions = (
            refresh_sessions
            if refresh_sessions is not None
            else RefreshSessionRegistry()
        )
        self._login_attempts = (
            login_attempts
            if login_attempts is not None
            else LoginAttemptLimiter()
        )
        self._audit_publisher = audit_publisher

    def login(self, username: str, password: str) -> TokenPair:
        """Authenticate credentials and issue an Atlas token pair."""

        normalized_username = username.strip()

        if not normalized_username or not password:
            self._audit(
                "security.authentication.failed",
                {
                    "username": normalized_username,
                    "reason": "missing_credentials",
                },
            )
            raise InvalidCredentialsError(
                "Username and password are required."
            )

        retry_after = self._login_attempts.retry_after(
            normalized_username
        )
        if retry_after is not None:
            self._audit(
                "security.authentication.throttled",
                {
                    "username": normalized_username,
                    "retry_after_seconds": retry_after,
                },
            )
            raise AuthenticationRateLimitError(retry_after)

        try:
            user = self._provider.authenticate(
                normalized_username,
                password,
            )
        except AuthenticationProviderError:
            self._audit(
                "security.authentication.failed",
                {
                    "username": normalized_username,
                    "reason": "provider_unavailable",
                },
            )
            raise

        if user is None:
            self._login_attempts.record_failure(
                normalized_username
            )
            self._audit(
                "security.authentication.failed",
                {
                    "username": normalized_username,
                    "reason": "invalid_credentials",
                },
            )
            raise InvalidCredentialsError(
                "Username or password is incorrect."
            )

        self._login_attempts.reset(normalized_username)
        tokens = self._issue_token_pair(user)
        self._audit(
            "security.authentication.succeeded",
            self._identity_payload(user),
        )
        return tokens

    def refresh(
        self,
        refresh_token: str,
        user: AuthenticatedUser,
    ) -> TokenPair:
        """Validate a refresh token and issue a replacement token pair."""

        try:
            claims = self._jwt_service.decode_token(
                refresh_token,
                expected_type=TokenType.REFRESH,
            )
        except TokenError:
            self._audit(
                "security.session.refresh_rejected",
                {
                    **self._identity_payload(user),
                    "reason": "invalid_or_expired",
                },
            )
            raise

        if claims.subject != user.user_id:
            self._audit(
                "security.session.refresh_rejected",
                {
                    **self._identity_payload(user),
                    "reason": "subject_mismatch",
                },
            )
            raise InvalidCredentialsError(
                "Refresh token does not belong to this user."
            )

        if not self._refresh_sessions.consume(claims):
            self._audit(
                "security.session.refresh_rejected",
                {
                    **self._identity_payload(user),
                    "reason": "inactive_or_replayed",
                },
            )
            raise InvalidCredentialsError(
                "Refresh token is no longer active."
            )

        tokens = self._issue_token_pair(user)
        self._audit(
            "security.session.refreshed",
            self._identity_payload(user),
        )
        return tokens

    def logout(
        self,
        refresh_token: str,
        user: AuthenticatedUser,
    ) -> None:
        """Revoke a structurally valid refresh session if active."""

        try:
            claims = self._jwt_service.decode_token(
                refresh_token,
                expected_type=TokenType.REFRESH,
            )
        except TokenError:
            self._audit(
                "security.session.revoke_rejected",
                {
                    **self._identity_payload(user),
                    "reason": "invalid_or_expired",
                },
            )
            raise

        if claims.subject != user.user_id:
            self._audit(
                "security.session.revoke_rejected",
                {
                    **self._identity_payload(user),
                    "reason": "subject_mismatch",
                },
            )
            raise InvalidCredentialsError(
                "Refresh token does not belong to this user."
            )

        self._refresh_sessions.revoke(claims)
        self._audit(
            "security.session.revoked",
            self._identity_payload(user),
        )

    def _audit(
        self,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self._audit_publisher is None:
            return

        self._audit_publisher(event_name, payload)

    @staticmethod
    def _identity_payload(user: AuthenticatedUser) -> dict[str, str]:
        return {
            "user_id": user.user_id,
            "username": user.username,
            "provider": user.provider,
        }

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
