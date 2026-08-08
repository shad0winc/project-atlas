"""Tracked contracts for public Atlas ingress exposure."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_MAIN = PROJECT_ROOT / "apps" / "api" / "atlas_api" / "main.py"
CADDY_SITE = PROJECT_ROOT / "infra" / "caddy" / "sites" / "atlas.caddy"


def test_fastapi_disables_public_documentation_and_schema_routes() -> None:
    content = API_MAIN.read_text(encoding="utf-8")

    assert "docs_url=None" in content
    assert "redoc_url=None" in content
    assert "openapi_url=None" in content
    assert 'docs_url="/api/docs"' not in content
    assert 'openapi_url="/api/openapi.json"' not in content


def test_caddy_explicitly_blocks_api_metadata_before_general_proxy() -> None:
    content = CADDY_SITE.read_text(encoding="utf-8")
    metadata = (
        "@atlas_api_metadata path /api/docs /api/docs/* "
        "/api/openapi.json /api/redoc /api/redoc/*"
    )

    assert metadata in content
    assert 'respond "Not Found" 404' in content
    assert content.index("@atlas_api_metadata path") < content.index("handle /api/*")
