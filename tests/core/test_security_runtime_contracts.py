"""Static release contracts for security-critical Atlas runtime wiring."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGRESS = PROJECT_ROOT / "stack" / "ingress.yml"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
API_MAIN = PROJECT_ROOT / "apps" / "api" / "atlas_api" / "main.py"


def test_ingress_requires_jwt_secret_for_api_service() -> None:
    """Compose must refuse an API service with no signing-secret source."""

    content = INGRESS.read_text(encoding="utf-8")

    assert (
        'ATLAS_JWT_SECRET: "${ATLAS_JWT_SECRET:?ATLAS_JWT_SECRET is required}"'
        in content
    )


def test_ingress_passes_bounded_authentication_settings() -> None:
    """Supported authentication settings cross the Compose boundary explicitly."""

    content = INGRESS.read_text(encoding="utf-8")

    assert 'ATLAS_JWT_ISSUER: "${ATLAS_JWT_ISSUER:-project-atlas}"' in content
    assert 'ATLAS_JWT_AUDIENCE: "${ATLAS_JWT_AUDIENCE:-atlas-portal}"' in content
    assert 'ATLAS_ACCESS_TOKEN_MINUTES: "${ATLAS_ACCESS_TOKEN_MINUTES:-15}"' in content
    assert 'ATLAS_REFRESH_TOKEN_DAYS: "${ATLAS_REFRESH_TOKEN_DAYS:-30}"' in content


def test_example_configuration_never_contains_a_default_signing_secret() -> None:
    """The tracked example names the secret but supplies no reusable value."""

    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    secret_lines = [line for line in lines if line.startswith("ATLAS_JWT_SECRET=")]

    assert secret_lines == ["ATLAS_JWT_SECRET="]


def test_api_lifespan_validates_authentication_settings() -> None:
    """Security configuration validation belongs to application startup."""

    content = API_MAIN.read_text(encoding="utf-8")

    assert "AtlasAPISettings.from_environment()" in content
    assert "lifespan=_lifespan" in content


def test_operational_compose_calls_use_explicit_operator_environment() -> None:
    """Normal update and verification commands must load the root operator env."""

    update = (PROJECT_ROOT / "scripts" / "commands" / "update.sh").read_text(
        encoding="utf-8"
    )
    verify = (PROJECT_ROOT / "scripts" / "verify-ingress.sh").read_text(
        encoding="utf-8"
    )

    assert update.count('--env-file "$ATLAS_PROJECT_DIR/.env"') == 5
    assert '--env-file "$PROJECT_DIR/.env"' in verify


def test_deployment_capture_and_recovery_preserve_operator_environment() -> None:
    """Deployment observation and rollback use the same preserved operator env."""

    deployment = (
        PROJECT_ROOT / "scripts" / "commands" / "deployment.sh"
    ).read_text(encoding="utf-8")

    assert '--env-file "$ATLAS_PROJECT_DIR/.env"' in deployment
    assert '--env-file "$recovery/.env"' in deployment
    assert 'ln -s -- "$ATLAS_PROJECT_DIR/.env" "$recovery/.env"' in deployment
