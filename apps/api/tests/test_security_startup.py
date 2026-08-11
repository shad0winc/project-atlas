"""Security-critical Atlas API startup tests."""

import pytest
from fastapi.testclient import TestClient

from atlas_api.core.settings import SettingsError
from atlas_api.main import create_app


def test_startup_rejects_missing_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """The API must not become runnable without its signing secret."""

    monkeypatch.delenv("ATLAS_JWT_SECRET", raising=False)

    with pytest.raises(SettingsError, match="ATLAS_JWT_SECRET"):
        with TestClient(create_app()):
            pass


def test_startup_rejects_short_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """A present but weak signing secret must fail startup too."""

    monkeypatch.setenv("ATLAS_JWT_SECRET", "too-short")

    with pytest.raises(SettingsError, match="ATLAS_JWT_SECRET"):
        with TestClient(create_app()):
            pass


def test_startup_accepts_valid_authentication_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid authentication settings permit normal API startup."""

    monkeypatch.setenv(
        "ATLAS_JWT_SECRET",
        "m023-26-runtime-startup-test-secret-00000001",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
