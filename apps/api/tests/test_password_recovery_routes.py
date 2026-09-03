"""HTTP contracts for unauthenticated password recovery."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_api.dependencies import (
    get_password_recovery_service,
)
from atlas_api.routes.v1.auth import router
from atlas_api.services.password_recovery import (
    PasswordRecoveryServiceError,
)


class FakeRecoveryService:
    def __init__(self) -> None:
        self.requested: list[str] = []
        self.resets: list[tuple[str, str]] = []
        self.reject_reset = False

    def request_reset(self, email: str) -> None:
        self.requested.append(email)

    def reset_password(
        self,
        *,
        token: str,
        new_password: str,
    ) -> None:
        if self.reject_reset:
            raise PasswordRecoveryServiceError(
                "Password recovery token is invalid or expired."
            )
        self.resets.append(
            (token, new_password)
        )


def _client(
    service: FakeRecoveryService,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[
        get_password_recovery_service
    ] = lambda: service

    return TestClient(app)


def test_request_returns_generic_accepted_response() -> None:
    service = FakeRecoveryService()

    response = _client(service).post(
        "/auth/password-recovery/request",
        json={"email": "member@example.test"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message": (
            "If an Atlas account exists for that email, "
            "a password reset link has been sent."
        ),
    }

    assert service.requested == [
        "member@example.test"
    ]


def test_request_requires_email() -> None:
    response = _client(
        FakeRecoveryService()
    ).post(
        "/auth/password-recovery/request",
        json={},
    )

    assert response.status_code == 422


def test_reset_consumes_token_and_password() -> None:
    service = FakeRecoveryService()

    response = _client(service).post(
        "/auth/password-recovery/reset",
        json={
            "token": "atlas_reset_example",
            "new_password": "new-secret",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "password-reset"
    }

    assert service.resets == [
        (
            "atlas_reset_example",
            "new-secret",
        )
    ]


def test_reset_invalid_token_is_generic_bad_request() -> None:
    service = FakeRecoveryService()
    service.reject_reset = True

    response = _client(service).post(
        "/auth/password-recovery/reset",
        json={
            "token": "atlas_reset_invalid",
            "new_password": "new-secret",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Password recovery token is invalid "
            "or expired."
        )
    }
