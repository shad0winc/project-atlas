"""Contract tests for the shared Discovery HTTP provider base."""

from dataclasses import FrozenInstanceError
from io import BytesIO
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError

import pytest

from atlas.discovery.providers import (
    BaseDiscoveryProvider,
    DiscoveryProviderError,
)


class StubProvider(BaseDiscoveryProvider):
    """Minimal concrete provider used to test shared HTTP behavior."""

    def list_indexers(self):
        return ()

    def list_categories(self):
        return ()

    def list_applications(self):
        return ()


class FakeResponse:
    """Context-managed in-memory HTTP response."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self._payload


def make_provider(**overrides) -> StubProvider:
    values = {
        "base_url": "http://prowlarr:9696",
        "api_key": "secret-key",
        "timeout": 10,
    }
    values.update(overrides)

    return StubProvider(**values)


def test_provider_normalizes_configuration() -> None:
    provider = StubProvider(
        base_url="  http://prowlarr:9696///  ",
        api_key="  secret-key  ",
        timeout=15,
    )

    assert provider.base_url == "http://prowlarr:9696"
    assert provider.api_key == "secret-key"
    assert provider.timeout == 15.0


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "   ",
        None,
        42,
    ],
)
def test_provider_rejects_missing_base_url(base_url: object) -> None:
    with pytest.raises(
        DiscoveryProviderError,
        match="base_url is required",
    ):
        StubProvider(
            base_url=base_url,  # type: ignore[arg-type]
            api_key="key",
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://prowlarr",
        "file:///tmp/prowlarr",
        "prowlarr:9696",
    ],
)
def test_provider_rejects_unsupported_url_scheme(
    base_url: str,
) -> None:
    with pytest.raises(
        DiscoveryProviderError,
        match="base_url must use http or https",
    ):
        StubProvider(
            base_url=base_url,
            api_key="key",
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://",
        "https://",
    ],
)
def test_provider_requires_url_host(base_url: str) -> None:
    with pytest.raises(
        DiscoveryProviderError,
        match="base_url must include a host",
    ):
        StubProvider(
            base_url=base_url,
            api_key="key",
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://prowlarr:9696?debug=true",
        "http://prowlarr:9696#fragment",
    ],
)
def test_provider_rejects_query_or_fragment(
    base_url: str,
) -> None:
    with pytest.raises(
        DiscoveryProviderError,
        match="base_url must not include a query or fragment",
    ):
        StubProvider(
            base_url=base_url,
            api_key="key",
        )


@pytest.mark.parametrize(
    "api_key",
    [
        "",
        "   ",
        None,
        42,
    ],
)
def test_provider_requires_api_key(api_key: object) -> None:
    with pytest.raises(
        DiscoveryProviderError,
        match="api_key is required",
    ):
        StubProvider(
            base_url="http://prowlarr:9696",
            api_key=api_key,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "timeout",
    [
        0,
        -1,
        True,
        False,
        "10",
        None,
    ],
)
def test_provider_requires_positive_numeric_timeout(
    timeout: object,
) -> None:
    with pytest.raises(
        DiscoveryProviderError,
        match="timeout must be a positive number",
    ):
        StubProvider(
            base_url="http://prowlarr:9696",
            api_key="key",
            timeout=timeout,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (
            "/api/v1/indexer",
            "http://prowlarr:9696/api/v1/indexer",
        ),
        (
            "api/v1/indexer",
            "http://prowlarr:9696/api/v1/indexer",
        ),
        (
            " /api/v1/health ",
            "http://prowlarr:9696/api/v1/health",
        ),
    ],
)
def test_build_url_normalizes_api_path(
    path: str,
    expected: str,
) -> None:
    provider = make_provider()

    assert provider._build_url(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "",
        "   ",
        None,
        42,
    ],
)
def test_build_url_requires_path(path: object) -> None:
    provider = make_provider()

    with pytest.raises(
        DiscoveryProviderError,
        match="path is required",
    ):
        provider._build_url(path)  # type: ignore[arg-type]


def test_headers_include_expected_values() -> None:
    provider = make_provider()

    assert provider._headers() == {
        "Accept": "application/json",
        "User-Agent": "Project-Atlas/Discovery",
        "X-Api-Key": "secret-key",
    }


def test_provider_repr_redacts_api_key() -> None:
    provider = make_provider(
        api_key="do-not-display",
    )

    representation = repr(provider)

    assert "do-not-display" not in representation
    assert "api_key" not in representation
    assert "http://prowlarr:9696" in representation


def test_provider_is_immutable() -> None:
    provider = make_provider()

    with pytest.raises(FrozenInstanceError):
        provider.timeout = 30  # type: ignore[misc]


def test_get_json_decodes_successful_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout

        return FakeResponse(
            b'{"name": "Prowlarr", "healthy": true}'
        )

    monkeypatch.setattr(
        "atlas.discovery.providers.base.urlopen",
        fake_urlopen,
    )

    provider = make_provider(
        timeout=17,
    )

    result = provider._get_json("/api/v1/health")

    assert result == {
        "name": "Prowlarr",
        "healthy": True,
    }
    assert captured["timeout"] == 17.0

    request = captured["request"]

    assert request.full_url == (
        "http://prowlarr:9696/api/v1/health"
    )
    assert request.get_method() == "GET"
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("User-agent") == (
        "Project-Atlas/Discovery"
    )
    assert request.get_header("X-api-key") == "secret-key"


def test_get_json_supports_array_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "atlas.discovery.providers.base.urlopen",
        lambda request, timeout: FakeResponse(
            b'[{"id": 1}, {"id": 2}]'
        ),
    )

    provider = make_provider()

    assert provider._get_json("/api/v1/indexer") == [
        {
            "id": 1,
        },
        {
            "id": 2,
        },
    ]


def test_get_json_translates_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            BytesIO(),
        )

    monkeypatch.setattr(
        "atlas.discovery.providers.base.urlopen",
        fake_urlopen,
    )

    provider = make_provider()

    with pytest.raises(
        DiscoveryProviderError,
        match=(
            "provider request failed with HTTP 401: "
            "http://prowlarr:9696/api/v1/indexer"
        ),
    ):
        provider._get_json("/api/v1/indexer")


def test_get_json_translates_url_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "atlas.discovery.providers.base.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(
            URLError("connection refused")
        ),
    )

    provider = make_provider()

    with pytest.raises(
        DiscoveryProviderError,
        match=(
            "provider request could not connect: "
            "http://prowlarr:9696/api/v1/indexer"
        ),
    ):
        provider._get_json("/api/v1/indexer")


@pytest.mark.parametrize(
    "exception",
    [
        SocketTimeout("timed out"),
        TimeoutError("timed out"),
    ],
)
def test_get_json_translates_timeout(
    monkeypatch: pytest.MonkeyPatch,
    exception: BaseException,
) -> None:
    def fake_urlopen(request, timeout):
        raise exception

    monkeypatch.setattr(
        "atlas.discovery.providers.base.urlopen",
        fake_urlopen,
    )

    provider = make_provider()

    with pytest.raises(
        DiscoveryProviderError,
        match=(
            "provider request could not connect: "
            "http://prowlarr:9696/api/v1/indexer"
        ),
    ):
        provider._get_json("/api/v1/indexer")


def test_get_json_translates_os_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "atlas.discovery.providers.base.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(
            OSError("socket failure")
        ),
    )

    provider = make_provider()

    with pytest.raises(
        DiscoveryProviderError,
        match=(
            "provider request failed: "
            "http://prowlarr:9696/api/v1/indexer"
        ),
    ):
        provider._get_json("/api/v1/indexer")


def test_get_json_rejects_non_utf8_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "atlas.discovery.providers.base.urlopen",
        lambda request, timeout: FakeResponse(
            b"\xff\xfe\xfa"
        ),
    )

    provider = make_provider()

    with pytest.raises(
        DiscoveryProviderError,
        match=(
            "provider returned non-UTF-8 content: "
            "http://prowlarr:9696/api/v1/indexer"
        ),
    ):
        provider._get_json("/api/v1/indexer")


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"not-json",
        b"{",
    ],
)
def test_get_json_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    monkeypatch.setattr(
        "atlas.discovery.providers.base.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    provider = make_provider()

    with pytest.raises(
        DiscoveryProviderError,
        match=(
            "provider returned invalid JSON: "
            "http://prowlarr:9696/api/v1/indexer"
        ),
    ):
        provider._get_json("/api/v1/indexer")
