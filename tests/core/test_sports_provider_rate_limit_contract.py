from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVIDER = ROOT / "modules/sports/src/providers/thesportsdb.py"
PRIVATE_API = ROOT / "modules/sports/src/private_api.py"


def test_provider_has_bounded_cache_and_rate_limit_circuit() -> None:
    source = PROVIDER.read_text(encoding="utf-8")

    assert "_CACHE_MAX_ENTRIES = 512" in source
    assert "_SEARCH_CACHE_TTL_SECONDS = 60" in source
    assert "_DISCOVERY_CACHE_TTL_SECONDS = 300" in source
    assert "_RATE_LIMIT_MAX_SECONDS = 300" in source
    assert "SportsProviderRateLimitError" in source
    assert "HTTPStatus.TOO_MANY_REQUESTS" in source
    assert "Retry-After" in source


def test_private_search_preserves_provider_rate_limit_contract() -> None:
    source = PRIVATE_API.read_text(encoding="utf-8")

    assert "sports_provider_rate_limited" in source
    assert "HTTPStatus.TOO_MANY_REQUESTS" in source
    assert '"Retry-After"' in source
    assert 'getattr(exc, "provider_rate_limited", False)' in source
