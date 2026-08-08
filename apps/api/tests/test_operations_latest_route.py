"""Tests for the latest persisted Atlas Operations report endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from atlas.operations import (
    FileOperationsRepository,
    OperationFinding,
    OperationsReport,
    OperationsReportNotFoundError,
    OperationsSection,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    clear_dependency_caches,
    get_operations_repository,
)
from atlas_api.main import create_app
from atlas_api.routes.v1.operations import (
    OPERATIONS_REPORT_NOT_FOUND_CODE,
    OPERATIONS_REPORT_NOT_FOUND_MESSAGE,
    require_operations_report_read,
)


GENERATED_AT = "2026-08-04T02:45:00Z"


def persisted_report() -> OperationsReport:
    """Return one deterministic persisted report fixture."""

    return OperationsReport(
        report_id="persisted-operations-report",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="4a2da832",
        generated_at=GENERATED_AT,
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(
                    OperationFinding(
                        identifier="system.memory",
                        name="Memory",
                        status="healthy",
                        severity="info",
                        message="Memory usage is healthy",
                        metadata={
                            "percent": 40,
                        },
                    ),
                ),
            ),
        ),
    )


class FakeOperationsRepository:
    """Deterministic repository used by latest-route tests."""

    def __init__(
        self,
        report: OperationsReport | None,
    ) -> None:
        self.report = report
        self.latest_count = 0

    def latest(self) -> OperationsReport:
        self.latest_count += 1

        if self.report is None:
            raise OperationsReportNotFoundError(
                "latest Operations report was not found"
            )

        return self.report


def authenticated_user() -> AuthenticatedUser:
    """Return one authenticated test operator."""

    return AuthenticatedUser(
        user_id="atlas-admin",
        username="admin",
        display_name="Atlas Administrator",
        roles=("administrator",),
        provider="jellyfin",
        metadata={},
    )


def test_latest_error_contract_constants_are_stable() -> None:
    assert OPERATIONS_REPORT_NOT_FOUND_CODE == (
        "operations_report_not_found"
    )
    assert OPERATIONS_REPORT_NOT_FOUND_MESSAGE == (
        "Latest Operations report was not found"
    )


def test_operations_repository_factory_uses_default_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "ATLAS_OPERATIONS_DIRECTORY",
        raising=False,
    )
    clear_dependency_caches()

    repository = get_operations_repository()

    assert isinstance(
        repository,
        FileOperationsRepository,
    )

    clear_dependency_caches()


def test_operations_repository_factory_uses_runtime_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_OPERATIONS_DIRECTORY",
        str(tmp_path),
    )
    clear_dependency_caches()

    repository = get_operations_repository()

    assert isinstance(
        repository,
        FileOperationsRepository,
    )
    assert repository.root == tmp_path

    clear_dependency_caches()


def test_operations_repository_factory_rejects_empty_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_OPERATIONS_DIRECTORY",
        "   ",
    )
    clear_dependency_caches()

    with pytest.raises(
        ValueError,
        match="ATLAS_OPERATIONS_DIRECTORY cannot be empty",
    ):
        get_operations_repository()

    clear_dependency_caches()


def test_dependency_cache_clear_rebuilds_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_OPERATIONS_DIRECTORY",
        str(tmp_path),
    )
    clear_dependency_caches()

    first = get_operations_repository()

    clear_dependency_caches()
    second = get_operations_repository()

    assert first is not second

    clear_dependency_caches()


def test_latest_endpoint_returns_persisted_report() -> None:
    app = create_app()
    repository = FakeOperationsRepository(
        persisted_report(),
    )

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/latest"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repository.latest_count == 1

    payload = response.json()

    assert payload["schema_version"] == 1
    assert payload["api_version"] == "v1"
    assert payload["success"] is True
    assert payload["generated_at"] == GENERATED_AT

    report = payload["data"]["report"]

    assert report["report_id"] == (
        "persisted-operations-report"
    )
    assert report["generated_at"] == GENERATED_AT
    assert report["status"] == "healthy"
    assert report["score"] == 100


def test_latest_endpoint_returns_failure_envelope_when_missing() -> None:
    app = create_app()
    repository = FakeOperationsRepository(None)

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/latest"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert repository.latest_count == 1

    payload = response.json()

    assert payload["schema_version"] == 1
    assert payload["api_version"] == "v1"
    assert payload["success"] is False
    assert payload["error"] == {
        "code": "operations_report_not_found",
        "message": "Latest Operations report was not found",
        "details": {
            "resource": "operations_report",
            "selector": "latest",
        },
    }


def test_latest_endpoint_does_not_collect_live_report() -> None:
    app = create_app()
    repository = FakeOperationsRepository(
        persisted_report(),
    )

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/latest"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repository.latest_count == 1


def test_openapi_registers_latest_success_and_failure() -> None:
    app = create_app()
    operation = app.openapi()["paths"][
        "/api/v1/operations/latest"
    ]["get"]

    assert operation["tags"] == ["operations"]
    assert operation["summary"] == (
        "Read the latest persisted Atlas Operations report"
    )

    success_schema = operation["responses"]["200"][
        "content"
    ]["application/json"]["schema"]

    failure_schema = operation["responses"]["404"][
        "content"
    ]["application/json"]["schema"]

    assert success_schema == {
        "$ref": (
            "#/components/schemas/"
            "ApiSuccessEnvelopeSchema"
        )
    }
    assert failure_schema == {
        "$ref": (
            "#/components/schemas/"
            "ApiFailureEnvelopeSchema"
        )
    }
