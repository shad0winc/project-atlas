"""HTTP contract tests for Atlas authentication token refresh."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas_api.auth.exceptions import InvalidCredentialsError
from atlas_api.auth.models import AuthenticatedUser, TokenPair
from atlas_api.dependencies import (
    get_authentication_service,
    get_jwt_service,
    get_security_audit_writer,
    get_user_profile_store,
)
from atlas_api.main import create_app


class SuccessfulRefreshAuthenticationService:
    """Authentication service double returning a rotated token pair."""

    def refresh(
        self,
        refresh_token: str,
        user: AuthenticatedUser,
    ) -> TokenPair:
        self.refresh_token = refresh_token
        self.user = user

        return TokenPair(
            access_token="replacement-access-token",
            refresh_token="replacement-refresh-token",
        )


class InvalidRefreshAuthenticationService:
    """Authentication service double rejecting token rotation."""

    def refresh(
        self,
        refresh_token: str,
        user: AuthenticatedUser,
    ) -> TokenPair:
        raise InvalidCredentialsError("refresh token user mismatch")


class AuthenticationRefreshRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = create_app()
        self.client = TestClient(self.application)

        self.jwt_service = object()
        self.profiles = object()
        self.audit_writer = object()

        self.application.dependency_overrides[
            get_jwt_service
        ] = lambda: self.jwt_service

        self.application.dependency_overrides[
            get_user_profile_store
        ] = lambda: self.profiles
        self.application.dependency_overrides[
            get_security_audit_writer
        ] = lambda: self.audit_writer

        self.user = AuthenticatedUser(
            user_id="user-123",
            username="michael",
            display_name="Michael",
            roles=("admin",),
            provider="jellyfin",
        )

    def tearDown(self) -> None:
        self.application.dependency_overrides.clear()

    def test_refresh_returns_rotated_token_pair(self) -> None:
        service = SuccessfulRefreshAuthenticationService()

        self.application.dependency_overrides[
            get_authentication_service
        ] = lambda: service

        with patch(
            "atlas_api.routes.v1.auth.resolve_refresh_user",
            return_value=self.user,
        ) as resolve_user:
            response = self.client.post(
                "/api/v1/auth/refresh",
                json={
                    "refresh_token": "original-refresh-token",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "access_token": "replacement-access-token",
                "refresh_token": "replacement-refresh-token",
                "token_type": "bearer",
            },
        )

        self.assertEqual(
            service.refresh_token,
            "original-refresh-token",
        )
        self.assertEqual(service.user, self.user)

        resolve_user.assert_called_once_with(
            "original-refresh-token",
            jwt_service=self.jwt_service,
            profiles=self.profiles,
            audit_writer=self.audit_writer,
        )

    def test_refresh_rejects_invalid_token_identity(self) -> None:
        self.application.dependency_overrides[
            get_authentication_service
        ] = SuccessfulRefreshAuthenticationService

        with patch(
            "atlas_api.routes.v1.auth.resolve_refresh_user",
            side_effect=HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired.",
                headers={"WWW-Authenticate": "Bearer"},
            ),
        ):
            response = self.client.post(
                "/api/v1/auth/refresh",
                json={
                    "refresh_token": "invalid-refresh-token",
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                "detail":
                    "Refresh token is invalid or expired."
            },
        )
        self.assertEqual(
            response.headers["www-authenticate"],
            "Bearer",
        )

    def test_refresh_rejects_service_identity_mismatch(self) -> None:
        self.application.dependency_overrides[
            get_authentication_service
        ] = InvalidRefreshAuthenticationService

        with patch(
            "atlas_api.routes.v1.auth.resolve_refresh_user",
            return_value=self.user,
        ):
            response = self.client.post(
                "/api/v1/auth/refresh",
                json={
                    "refresh_token":
                        "mismatched-refresh-token"
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                "detail":
                    "Refresh token is invalid or expired."
            },
        )
        self.assertEqual(
            response.headers["www-authenticate"],
            "Bearer",
        )

    def test_refresh_rejects_empty_token(self) -> None:
        self.application.dependency_overrides[
            get_authentication_service
        ] = SuccessfulRefreshAuthenticationService

        response = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": ""},
        )

        self.assertEqual(response.status_code, 422)

    def test_refresh_rejects_unknown_request_fields(self) -> None:
        self.application.dependency_overrides[
            get_authentication_service
        ] = SuccessfulRefreshAuthenticationService

        response = self.client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "refresh-token",
                "access_token": "not-allowed",
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
