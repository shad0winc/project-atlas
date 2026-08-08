"""Security tests for Atlas API metadata exposure."""

from fastapi.testclient import TestClient

from atlas_api.main import create_app


def test_api_documentation_and_schema_routes_are_not_http_exposed() -> None:
    app = create_app()
    client = TestClient(app)

    for path in (
        "/api/docs",
        "/api/docs/",
        "/api/openapi.json",
        "/api/redoc",
        "/api/redoc/",
    ):
        response = client.get(path)
        assert response.status_code == 404, path


def test_internal_openapi_contract_remains_available_for_validation() -> None:
    schema = create_app().openapi()

    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
