"""Contract tests for media-request HTTP provider foundations."""

from __future__ import annotations

from io import BytesIO
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError
from urllib.request import Request
from unittest.mock import patch

import pytest

from atlas.media_requests import (
    BaseMediaRequestHTTPProvider,
    MediaRequest,
    MediaRequestHTTPError,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatusResult,
    ProviderSubmissionResult,
)


class ResponseStub:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.read_count = 0

    def __enter__(self) -> "ResponseStub":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None

    def read(self) -> bytes:
        self.read_count += 1
        return self.payload


class ConcreteHTTPProvider(BaseMediaRequestHTTPProvider):
    @property
    def name(self) -> str:
        return "example"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(media_types=("movie",))

    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        raise NotImplementedError

    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        raise NotImplementedError

    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        raise NotImplementedError

    def health(self) -> ProviderHealth:
        raise NotImplementedError

    def get_json(self, path: object) -> object:
        return self._get_json(path)

    def post_json(self, path: object, payload: object) -> object:
        return self._post_json(path, payload)

    def delete_json(self, path: object) -> object:
        return self._delete_json(path)

    def request_json(
        self,
        method: object,
        path: object,
        *,
        payload: object | None = None,
    ) -> object:
        return self._request_json(method, path, payload=payload)

    def build_url(self, path: object) -> str:
        return self._build_url(path)

    def headers(
        self,
        *,
        include_content_type: bool = False,
    ) -> dict[str, str]:
        return self._headers(
            include_content_type=include_content_type,
        )


def make_provider(**overrides: object) -> ConcreteHTTPProvider:
    values: dict[str, object] = {
        "base_url": "http://127.0.0.1:5055",
        "api_key": "secret-api-key",
    }
    values.update(overrides)
    return ConcreteHTTPProvider(**values)


def request_header(request: Request, name: str) -> str | None:
    target = name.casefold()
    for key, value in request.header_items():
        if key.casefold() == target:
            return value
    return None


def test_provider_normalizes_configuration() -> None:
    provider = make_provider(
        base_url=" https://example.test/base/ ",
        api_key=" secret ",
        timeout=5,
        user_agent=" Atlas Test ",
    )

    assert provider.base_url == "https://example.test/base"
    assert provider.api_key == "secret"
    assert provider.timeout == 5.0
    assert provider.user_agent == "Atlas Test"


def test_api_key_is_hidden_from_repr() -> None:
    rendered = repr(make_provider())
    assert "secret-api-key" not in rendered
    assert "api_key" not in rendered


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "example.test",
        "ftp://example.test",
        "http:///missing-host",
        "http://user:pass@example.test",
        "http://example.test?query=1",
        "http://example.test#fragment",
    ],
)
def test_provider_rejects_invalid_base_url(base_url: str) -> None:
    with pytest.raises(MediaRequestHTTPError, match="base_url"):
        make_provider(base_url=base_url)


@pytest.mark.parametrize("api_key", ["", "   ", None, True])
def test_provider_requires_api_key(api_key: object) -> None:
    with pytest.raises(MediaRequestHTTPError, match="api_key"):
        make_provider(api_key=api_key)


@pytest.mark.parametrize("timeout", [0, -1, True, "10", None])
def test_provider_rejects_invalid_timeout(timeout: object) -> None:
    with pytest.raises(MediaRequestHTTPError, match="timeout"):
        make_provider(timeout=timeout)


@pytest.mark.parametrize("user_agent", ["", "   ", None, True])
def test_provider_requires_user_agent(user_agent: object) -> None:
    with pytest.raises(MediaRequestHTTPError, match="user_agent"):
        make_provider(user_agent=user_agent)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/v1/status", "http://127.0.0.1:5055/api/v1/status"),
        ("api/v1/status", "http://127.0.0.1:5055/api/v1/status"),
        (
            "/api/v1/request/1?include=media",
            "http://127.0.0.1:5055/api/v1/request/1?include=media",
        ),
    ],
)
def test_build_url_normalizes_relative_paths(
    path: str,
    expected: str,
) -> None:
    assert make_provider().build_url(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "",
        None,
        True,
        "https://other.example/api",
        "//other.example/api",
        "/api/v1/status#fragment",
    ],
)
def test_build_url_rejects_unsafe_path(path: object) -> None:
    with pytest.raises(MediaRequestHTTPError, match="path"):
        make_provider().build_url(path)


def test_headers_include_authentication_and_user_agent() -> None:
    assert make_provider().headers() == {
        "Accept": "application/json",
        "User-Agent": "Project-Atlas/Media-Requests",
        "X-Api-Key": "secret-api-key",
    }


def test_content_type_is_added_only_for_json_body() -> None:
    provider = make_provider()
    assert "Content-Type" not in provider.headers()
    assert provider.headers(
        include_content_type=True
    )["Content-Type"] == "application/json"


def test_headers_require_boolean_content_type_flag() -> None:
    with pytest.raises(
        MediaRequestHTTPError,
        match="include_content_type",
    ):
        make_provider().headers(
            include_content_type=1,  # type: ignore[arg-type]
        )


def test_get_json_builds_authenticated_request() -> None:
    response = ResponseStub(b'{"status":"ok"}')

    with patch(
        "atlas.media_requests.providers.base.urlopen",
        return_value=response,
    ) as opener:
        result = make_provider(timeout=7).get_json(
            "/api/v1/status"
        )

    assert result == {"status": "ok"}
    request = opener.call_args.args[0]
    assert isinstance(request, Request)
    assert request.full_url == "http://127.0.0.1:5055/api/v1/status"
    assert request.get_method() == "GET"
    assert request.data is None
    assert request_header(request, "X-Api-Key") == "secret-api-key"
    assert opener.call_args.kwargs == {"timeout": 7.0}
    assert response.read_count == 1


def test_post_json_encodes_deterministic_utf8_json() -> None:
    response = ResponseStub(b'{"id":42}')

    with patch(
        "atlas.media_requests.providers.base.urlopen",
        return_value=response,
    ) as opener:
        result = make_provider().post_json(
            "/api/v1/request",
            {
                "mediaType": "movie",
                "mediaId": 157336,
                "title": "Amélie",
            },
        )

    assert result == {"id": 42}
    request = opener.call_args.args[0]
    assert request.get_method() == "POST"
    assert request_header(request, "Content-Type") == "application/json"
    assert request.data == (
        b'{"mediaId":157336,"mediaType":"movie",'
        b'"title":"Am\xc3\xa9lie"}'
    )


def test_delete_json_builds_delete_request() -> None:
    response = ResponseStub(b'{"deleted":true}')

    with patch(
        "atlas.media_requests.providers.base.urlopen",
        return_value=response,
    ) as opener:
        result = make_provider().delete_json("/api/v1/request/42")

    assert result == {"deleted": True}
    request = opener.call_args.args[0]
    assert request.get_method() == "DELETE"
    assert request.data is None
    assert request_header(request, "Content-Type") is None


def test_empty_response_returns_none() -> None:
    with patch(
        "atlas.media_requests.providers.base.urlopen",
        return_value=ResponseStub(b""),
    ):
        assert make_provider().delete_json(
            "/api/v1/request/42"
        ) is None


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_bodyless_methods_reject_payload(method: str) -> None:
    with pytest.raises(MediaRequestHTTPError, match="must not include"):
        make_provider().request_json(method, "/api", payload={})


def test_post_requires_payload() -> None:
    with pytest.raises(MediaRequestHTTPError, match="require a payload"):
        make_provider().request_json("POST", "/api")


def test_post_rejects_non_serializable_payload() -> None:
    with pytest.raises(
        MediaRequestHTTPError,
        match="not JSON serializable",
    ):
        make_provider().post_json("/api", {"value": object()})


@pytest.mark.parametrize("method", ["", "PATCH", "PUT", None, True])
def test_request_rejects_unsupported_method(method: object) -> None:
    with pytest.raises(MediaRequestHTTPError, match="method"):
        make_provider().request_json(method, "/api")


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 500])
def test_http_errors_are_normalized_without_secret(
    status_code: int,
) -> None:
    error = HTTPError(
        url="http://127.0.0.1:5055/api/v1/status",
        code=status_code,
        msg="failed",
        hdrs=None,
        fp=BytesIO(b'{"message":"secret-api-key"}'),
    )

    with patch(
        "atlas.media_requests.providers.base.urlopen",
        side_effect=error,
    ):
        with pytest.raises(
            MediaRequestHTTPError,
            match=f"HTTP {status_code}",
        ) as captured:
            make_provider().get_json("/api/v1/status")

    assert "secret-api-key" not in str(captured.value)


@pytest.mark.parametrize(
    "error",
    [
        URLError("connection refused"),
        SocketTimeout("timed out"),
        TimeoutError("timed out"),
    ],
)
def test_connection_errors_are_normalized(error: Exception) -> None:
    with patch(
        "atlas.media_requests.providers.base.urlopen",
        side_effect=error,
    ):
        with pytest.raises(
            MediaRequestHTTPError,
            match="could not connect",
        ):
            make_provider().get_json("/api/v1/status")


def test_os_errors_are_normalized() -> None:
    with patch(
        "atlas.media_requests.providers.base.urlopen",
        side_effect=OSError("failure"),
    ):
        with pytest.raises(
            MediaRequestHTTPError,
            match="request failed",
        ):
            make_provider().get_json("/api/v1/status")


def test_non_utf8_response_is_rejected() -> None:
    with patch(
        "atlas.media_requests.providers.base.urlopen",
        return_value=ResponseStub(b"\xff\xfe"),
    ):
        with pytest.raises(
            MediaRequestHTTPError,
            match="non-UTF-8",
        ):
            make_provider().get_json("/api/v1/status")


@pytest.mark.parametrize("payload", [b"{invalid", b"not-json"])
def test_invalid_json_response_is_rejected(payload: bytes) -> None:
    with patch(
        "atlas.media_requests.providers.base.urlopen",
        return_value=ResponseStub(payload),
    ):
        with pytest.raises(
            MediaRequestHTTPError,
            match="invalid JSON",
        ):
            make_provider().get_json("/api/v1/status")
