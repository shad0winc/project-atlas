from pathlib import Path

from atlas_api.services.sports import SportsProviderRateLimitError


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "apps/api/atlas_api/services/sports.py"
ROUTES = ROOT / "apps/api/atlas_api/routes/v1/sports.py"


def test_rate_limit_exception_bounds_retry_after() -> None:
    assert SportsProviderRateLimitError("limited", 0).retry_after_seconds == 1
    assert SportsProviderRateLimitError("limited", 45).retry_after_seconds == 45
    assert SportsProviderRateLimitError("limited", 99999).retry_after_seconds == 300


def test_writer_transport_preserves_private_rate_limit_code() -> None:
    source = SERVICE.read_text(encoding="utf-8")

    assert 'code == "sports_provider_rate_limited"' in source
    assert 'exc.headers.get("Retry-After", "60")' in source
    assert "raise SportsProviderRateLimitError(" in source


def test_public_search_routes_preserve_429_and_retry_after() -> None:
    source = ROUTES.read_text(encoding="utf-8")

    assert source.count(
        "except SportsProviderRateLimitError as error:"
    ) == 3
    assert source.count(
        "status_code=status.HTTP_429_TOO_MANY_REQUESTS"
    ) == 3
    assert source.count(
        '"Retry-After": str(error.retry_after_seconds)'
    ) == 3


def test_generic_search_transport_failure_remains_503() -> None:
    source = ROUTES.read_text(encoding="utf-8")

    assert source.count(
        "except (SportsProviderNotFoundError, SportsWriterTransportError) as error:"
    ) == 3
    assert source.count(
        "status.HTTP_503_SERVICE_UNAVAILABLE"
    ) >= 2
