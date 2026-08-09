"""HTTP contract tests for Atlas refresh-session logout."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_authentication_service,
    get_jwt_service,
    get_security_audit_writer,
    get_user_profile_store,
)
from atlas_api.main import create_app


class LogoutAuthenticationServiceDouble:
    def logout(
        self,
        refresh_token: str,
        user: AuthenticatedUser,
    ) -> None:
        self.refresh_token = refresh_token
        self.user = user


class AuthenticationLogoutRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = create_app()
        self.client = TestClient(self.application)
        self.jwt_service = object()
        self.profiles = object()
        self.audit_writer = object()
        self.service = LogoutAuthenticationServiceDouble()

        self.application.dependency_overrides[
            get_authentication_service
        ] = lambda: self.service
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
            roles=("member",),
        )

    def tearDown(self) -> None:
        self.application.dependency_overrides.clear()

    def test_logout_revokes_supplied_refresh_session(self) -> None:
        with patch(
            "atlas_api.routes.v1.auth.resolve_refresh_user",
            return_value=self.user,
        ) as resolve_user:
            response = self.client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": "current-refresh-token"},
            )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(
            self.service.refresh_token,
            "current-refresh-token",
        )
        self.assertEqual(self.service.user, self.user)
        resolve_user.assert_called_once_with(
            "current-refresh-token",
            jwt_service=self.jwt_service,
            profiles=self.profiles,
            audit_writer=self.audit_writer,
        )

    def test_logout_rejects_invalid_refresh_identity(self) -> None:
        with patch(
            "atlas_api.routes.v1.auth.resolve_refresh_user",
            side_effect=HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired.",
                headers={"WWW-Authenticate": "Bearer"},
            ),
        ):
            response = self.client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": "invalid-refresh-token"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "Refresh token is invalid or expired."},
        )

    def test_logout_rejects_empty_refresh_token(self) -> None:
        response = self.client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": ""},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
