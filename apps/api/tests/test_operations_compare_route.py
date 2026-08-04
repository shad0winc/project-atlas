"""Tests for the Atlas Operations comparison endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.operations import (
    OperationFinding,
    OperationsComparisonService,
    OperationsReport,
    OperationsSection,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    clear_dependency_caches,
    get_operations_comparison_service,
    get_operations_repository,
)
from atlas_api.main import create_app
from atlas_api.routes.v1.operations import (
    OPERATIONS_COMPARISON_HISTORY_LIMIT,
    OPERATIONS_COMPARISON_UNAVAILABLE_CODE,
    OPERATIONS_COMPARISON_UNAVAILABLE_MESSAGE,
    require_operations_report_read,
)


def make_report(
    *,
    report_id: str,
    generated_at: str,
    warning: bool,
) -> OperationsReport:
    """Return one deterministic comparison report."""

    return OperationsReport(
        report_id=report_id,
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="d0105425",
        generated_at=generated_at,
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(
                    OperationFinding(
                        identifier="system.memory",
                        name="Memory",
                        status=(
                            "warning"
                            if warning
                            else "healthy"
                        ),
                        severity=(
                            "warning"
                            if warning
                            else "info"
                        ),
                        message=(
                            "Memory usage is elevated"
                            if warning
                            else "Memory usage is healthy"
                        ),
                        metadata={
                            "percent": 90 if warning else 40,
                        },
                    ),
                ),
            ),
        ),
    )


class FakeOperationsRepository:
    """Deterministic repository for comparison-route tests."""

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


class RecordingComparisonService:
    """Record comparison calls while using the real domain service."""

    def __init__(self) -> None:
        self.calls: list[
            tuple[
                OperationsReport,
                OperationsReport,
                bool,
            ]
        ] = []
        self._service = OperationsComparisonService()

    def compare(
        self,
        previous: OperationsReport,
        current: OperationsReport,
        *,
        include_unchanged: bool = False,
    ):
        self.calls.append(
            (
                previous,
                current,
                include_unchanged,
            )
        )

        return self._service.compare(
            previous,
            current,
            include_unchanged=include_unchanged,
        )


def authenticated_user() -> AuthenticatedUser:
    """Return one authenticated Operations reader."""

    return AuthenticatedUser(
        user_id="atlas-admin",
        username="admin",
        display_name="Atlas Administrator",
        roles=("administrator",),
        provider="jellyfin",
        metadata={},
    )


def reports() -> tuple[OperationsReport, ...]:
    """Return newest-first comparison fixtures."""

    return (
        make_report(
            report_id="current-report",
            generated_at="2026-08-04T03:00:00Z",
            warning=True,
        ),
        make_report(
            report_id="previous-report",
            generated_at="2026-08-04T02:00:00Z",
            warning=False,
        ),
    )


def test_comparison_constants_are_stable() -> None:
    assert OPERATIONS_COMPARISON_HISTORY_LIMIT == 2
    assert OPERATIONS_COMPARISON_UNAVAILABLE_CODE == (
        "operations_comparison_unavailable"
    )
    assert OPERATIONS_COMPARISON_UNAVAILABLE_MESSAGE == (
        "At least two persisted Operations reports are required"
    )


def test_comparison_service_dependency_is_cached() -> None:
    clear_dependency_caches()

    first = get_operations_comparison_service()
    second = get_operations_comparison_service()

    assert isinstance(
        first,
        OperationsComparisonService,
    )
    assert first is second

    clear_dependency_caches()

    third = get_operations_comparison_service()

    assert third is not first

    clear_dependency_caches()


def test_compare_endpoint_uses_two_newest_reports() -> None:
    app = create_app()
    repository = FakeOperationsRepository(reports())
    service = RecordingComparisonService()

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository
    app.dependency_overrides[
        get_operations_comparison_service
    ] = lambda: service

    try:
        response = TestClient(app).get(
            "/api/v1/operations/compare"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repository.history_limits == [2]
    assert len(service.calls) == 1

    previous, current, include_unchanged = service.calls[0]

    assert previous.report_id == "previous-report"
    assert current.report_id == "current-report"
    assert include_unchanged is False

    payload = response.json()

    assert payload["schema_version"] == 1
    assert payload["api_version"] == "v1"
    assert payload["success"] is True

    comparison = payload["data"]["comparison"]

    assert comparison["previous"]["report_id"] == (
        "previous-report"
    )
    assert comparison["current"]["report_id"] == (
        "current-report"
    )
    assert comparison["summary"]["status_changed"] is True
    assert comparison["summary"]["score_delta"] == -50
    assert comparison["summary"]["changed_count"] == 1
    assert comparison["summary"]["difference_count"] == 1


def test_compare_endpoint_can_include_unchanged() -> None:
    app = create_app()
    current = make_report(
        report_id="current-report",
        generated_at="2026-08-04T03:00:00Z",
        warning=False,
    )
    previous = make_report(
        report_id="previous-report",
        generated_at="2026-08-04T02:00:00Z",
        warning=False,
    )
    repository = FakeOperationsRepository(
        (
            current,
            previous,
        ),
    )
    service = RecordingComparisonService()

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository
    app.dependency_overrides[
        get_operations_comparison_service
    ] = lambda: service

    try:
        response = TestClient(app).get(
            "/api/v1/operations/compare",
            params={
                "include_unchanged": "true",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.calls[0][2] is True

    comparison = response.json()["data"]["comparison"]

    assert comparison["summary"]["unchanged_count"] == 1
    assert comparison["summary"]["difference_count"] == 0
    assert len(comparison["changes"]) == 1
    assert comparison["changes"][0]["change_type"] == (
        "unchanged"
    )


def test_compare_endpoint_returns_conflict_when_history_is_short() -> None:
    app = create_app()
    repository = FakeOperationsRepository(
        (
            reports()[0],
        ),
    )
    service = RecordingComparisonService()

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository
    app.dependency_overrides[
        get_operations_comparison_service
    ] = lambda: service

    try:
        response = TestClient(app).get(
            "/api/v1/operations/compare"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert repository.history_limits == [2]
    assert service.calls == []

    assert response.json()["error"] == {
        "code": "operations_comparison_unavailable",
        "message": (
            "At least two persisted Operations reports are required"
        ),
        "details": {
            "available_reports": 1,
            "required_reports": 2,
            "resource": "operations_comparison",
        },
    }


def test_compare_endpoint_handles_empty_history() -> None:
    app = create_app()
    repository = FakeOperationsRepository(())
    service = RecordingComparisonService()

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository
    app.dependency_overrides[
        get_operations_comparison_service
    ] = lambda: service

    try:
        response = TestClient(app).get(
            "/api/v1/operations/compare"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["details"][
        "available_reports"
    ] == 0
    assert service.calls == []


def test_compare_endpoint_rejects_invalid_boolean() -> None:
    app = create_app()
    repository = FakeOperationsRepository(reports())
    service = RecordingComparisonService()

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository
    app.dependency_overrides[
        get_operations_comparison_service
    ] = lambda: service

    try:
        response = TestClient(app).get(
            "/api/v1/operations/compare",
            params={
                "include_unchanged": "invalid",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.history_limits == []
    assert service.calls == []


def test_compare_endpoint_does_not_mutate_reports() -> None:
    app = create_app()
    comparison_reports = reports()
    before = tuple(
        report.to_dict()
        for report in comparison_reports
    )
    repository = FakeOperationsRepository(
        comparison_reports,
    )
    service = RecordingComparisonService()

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_repository
    ] = lambda: repository
    app.dependency_overrides[
        get_operations_comparison_service
    ] = lambda: service

    try:
        response = TestClient(app).get(
            "/api/v1/operations/compare"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert tuple(
        report.to_dict()
        for report in comparison_reports
    ) == before


def test_openapi_registers_comparison_contract() -> None:
    app = create_app()
    response = TestClient(app).get(
        "/api/openapi.json"
    )

    assert response.status_code == 200

    operation = response.json()["paths"][
        "/api/v1/operations/compare"
    ]["get"]

    assert operation["tags"] == ["operations"]
    assert operation["summary"] == (
        "Compare the two newest Atlas Operations reports"
    )

    parameters = {
        parameter["name"]: parameter
        for parameter in operation["parameters"]
    }

    include_unchanged = parameters[
        "include_unchanged"
    ]

    assert include_unchanged["in"] == "query"
    assert include_unchanged["required"] is False
    assert include_unchanged["schema"]["default"] is False
    assert include_unchanged["schema"]["type"] == "boolean"

    success_schema = operation["responses"]["200"][
        "content"
    ]["application/json"]["schema"]

    conflict_schema = operation["responses"]["409"][
        "content"
    ]["application/json"]["schema"]

    assert success_schema == {
        "$ref": (
            "#/components/schemas/"
            "ApiSuccessEnvelopeSchema"
        )
    }
    assert conflict_schema == {
        "$ref": (
            "#/components/schemas/"
            "ApiFailureEnvelopeSchema"
        )
    }
