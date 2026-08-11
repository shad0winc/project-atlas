"""HTTP contract tests for Atlas login throttling."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from atlas_api.auth.exceptions import AuthenticationRateLimitError
from atlas_api.dependencies import get_authentication_service
from atlas_api.main import create_app


class ThrottledAuthenticationService:
    def login(self, username: str, password: str):
        raise AuthenticationRateLimitError(47)


class AuthenticationRateLimitRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = create_app()
        self.client = TestClient(self.application)
        self.application.dependency_overrides[
            get_authentication_service
        ] = ThrottledAuthenticationService

    def tearDown(self) -> None:
        self.application.dependency_overrides.clear()

    def test_login_throttle_returns_generic_429_and_retry_after(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "michael",
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            response.json(),
            {
                "detail":
                    "Too many authentication attempts. Try again later."
            },
        )
        self.assertEqual(response.headers["retry-after"], "47")


if __name__ == "__main__":
    unittest.main()
