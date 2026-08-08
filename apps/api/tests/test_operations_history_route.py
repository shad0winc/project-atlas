"""Tests for the persisted Atlas Operations history endpoint."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from atlas.operations import (
    OperationFinding,
    OperationsReport,
    OperationsSection,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_operations_repository
from atlas_api.main import create_app
from atlas_api.routes.v1.operations import (
    OPERATIONS_HISTORY_DEFAULT_LIMIT,
    OPERATIONS_HISTORY_MAX_LIMIT,
    require_operations_report_read,
)


def make_report(
    *,
    report_id: str,
    generated_at: str,
) -> OperationsReport:
    """Return one deterministic persisted report fixture."""

    return OperationsReport(
        report_id=report_id,
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="4e8fe94a",
        generated_at=generated_at,
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
    """Deterministic repository for history-route tests."""

    def __init__(
        self,
        reports: tuple[OperationsReport, ...],
    ) -> None:
        self.reports = reports
        self.history_limits: list[int] = []

    def history(
        self,
        limit: int = 25,
    ) -> tuple[OperationsReport, ...]:
        self.history_limits.append(limit)
        return self.reports[:limit]


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


def test_history_limit_constants_are_stable() -> None:
    assert OPERATIONS_HISTORY_DEFAULT_LIMIT == 25
    assert OPERATIONS_HISTORY_MAX_LIMIT == 100


def test_history_endpoint_uses_default_limit() -> None:
    app = create_app()
    repository = FakeOperationsRepository(
        (
            make_report(
                report_id="newest",
                generated_at="2026-08-04T03:00:00Z",
            ),
            make_report(
                report_id="older",
                generated_at="2026-08-04T02:00:00Z",
            ),
        ),
    )

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/history"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repository.history_limits == [25]

    payload = response.json()

    assert payload["schema_version"] == 1
    assert payload["api_version"] == "v1"
    assert payload["success"] is True
    assert payload["data"]["count"] == 2
    assert [
        report["report_id"]
        for report in payload["data"]["reports"]
    ] == [
        "newest",
        "older",
    ]

    generated_at = payload["generated_at"]
    parsed = datetime.fromisoformat(
        generated_at.replace("Z", "+00:00")
    )

    assert parsed.tzinfo is not None


def test_history_endpoint_applies_requested_limit() -> None:
    app = create_app()
    repository = FakeOperationsRepository(
        (
            make_report(
                report_id="newest",
                generated_at="2026-08-04T03:00:00Z",
            ),
            make_report(
                report_id="older",
                generated_at="2026-08-04T02:00:00Z",
            ),
        ),
    )

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/history",
            params={
                "limit": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repository.history_limits == [1]
    assert response.json()["data"]["count"] == 1
    assert response.json()["data"]["reports"][0][
        "report_id"
    ] == "newest"


def test_history_endpoint_returns_empty_collection() -> None:
    app = create_app()
    repository = FakeOperationsRepository(())

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/history"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repository.history_limits == [25]
    assert response.json()["data"] == {
        "count": 0,
        "reports": [],
    }


def test_history_endpoint_rejects_limit_below_minimum() -> None:
    app = create_app()
    repository = FakeOperationsRepository(())

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/history",
            params={
                "limit": 0,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.history_limits == []


def test_history_endpoint_rejects_limit_above_maximum() -> None:
    app = create_app()
    repository = FakeOperationsRepository(())

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/history",
            params={
                "limit": 101,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.history_limits == []


def test_history_endpoint_rejects_non_integer_limit() -> None:
    app = create_app()
    repository = FakeOperationsRepository(())

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/history",
            params={
                "limit": "invalid",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.history_limits == []


def test_history_endpoint_does_not_mutate_reports() -> None:
    app = create_app()
    report = make_report(
        report_id="immutable",
        generated_at="2026-08-04T03:00:00Z",
    )
    before = report.to_dict()
    repository = FakeOperationsRepository((report,))

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository

    try:
        response = TestClient(app).get(
            "/api/v1/operations/history"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert report.to_dict() == before


def test_openapi_registers_history_query_contract() -> None:
    app = create_app()
    operation = app.openapi()["paths"][
        "/api/v1/operations/history"
    ]["get"]

    assert operation["tags"] == ["operations"]
    assert operation["summary"] == (
        "Read persisted Atlas Operations report history"
    )

    parameters = {
        parameter["name"]: parameter
        for parameter in operation["parameters"]
    }

    limit = parameters["limit"]

    assert limit["in"] == "query"
    assert limit["required"] is False
    assert limit["schema"]["default"] == 25
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 100

    response_schema = operation["responses"]["200"][
        "content"
    ]["application/json"]["schema"]

    assert response_schema == {
        "$ref": (
            "#/components/schemas/"
            "ApiSuccessEnvelopeSchema"
        )
    }
