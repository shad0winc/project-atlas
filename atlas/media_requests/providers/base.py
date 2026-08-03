"""Shared HTTP foundations for concrete media-request providers."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from json import JSONDecodeError, dumps, loads
from socket import timeout as SocketTimeout
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from ..provider import MediaRequestProvider, MediaRequestProviderOperationError


class MediaRequestHTTPError(MediaRequestProviderOperationError):
    """Raised when a media-request provider HTTP operation fails."""


@dataclass(frozen=True)
class BaseMediaRequestHTTPProvider(MediaRequestProvider, ABC):
    """Shared authenticated JSON transport for request providers."""

    base_url: str
    api_key: str = field(repr=False)
    timeout: float = 10.0
    user_agent: str = "Project-Atlas/Media-Requests"

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", _normalize_base_url(self.base_url))
        object.__setattr__(self, "api_key", _required_text(self.api_key, "api_key"))
        object.__setattr__(
            self,
            "user_agent",
            _required_text(self.user_agent, "user_agent"),
        )

        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or self.timeout <= 0
        ):
            raise MediaRequestHTTPError("timeout must be a positive number")

        object.__setattr__(self, "timeout", float(self.timeout))

    def _build_url(self, path: object) -> str:
        normalized_path = _required_text(path, "path")
        parsed = urlparse(normalized_path)

        if parsed.scheme or parsed.netloc:
            raise MediaRequestHTTPError("path must be relative to base_url")
        if parsed.fragment:
            raise MediaRequestHTTPError("path must not include a fragment")

        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"

        return urljoin(
            f"{self.base_url}/",
            normalized_path.lstrip("/"),
        )

    def _headers(self, *, include_content_type: bool = False) -> dict[str, str]:
        if not isinstance(include_content_type, bool):
            raise MediaRequestHTTPError(
                "include_content_type must be a boolean",
            )

        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "X-Api-Key": self.api_key,
        }
        if include_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def _get_json(self, path: object) -> Any:
        return self._request_json("GET", path)

    def _post_json(self, path: object, payload: object) -> Any:
        return self._request_json("POST", path, payload=payload)

    def _delete_json(self, path: object) -> Any:
        return self._request_json("DELETE", path)

    def _request_json(
        self,
        method: object,
        path: object,
        *,
        payload: object | None = None,
    ) -> Any:
        normalized_method = _normalize_method(method)

        if normalized_method in {"GET", "DELETE"} and payload is not None:
            raise MediaRequestHTTPError(
                f"{normalized_method} requests must not include a payload",
            )

        data: bytes | None = None
        if normalized_method == "POST":
            if payload is None:
                raise MediaRequestHTTPError("POST requests require a payload")
            try:
                data = dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise MediaRequestHTTPError(
                    "provider request payload is not JSON serializable",
                ) from exc

        url = self._build_url(path)
        request = Request(
            url=url,
            data=data,
            headers=self._headers(include_content_type=data is not None),
            method=normalized_method,
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_payload = response.read()
        except HTTPError as exc:
            raise MediaRequestHTTPError(
                f"provider request failed with HTTP {exc.code}: "
                f"{normalized_method} {url}",
            ) from exc
        except (URLError, SocketTimeout, TimeoutError) as exc:
            raise MediaRequestHTTPError(
                f"provider request could not connect: {normalized_method} {url}",
            ) from exc
        except OSError as exc:
            raise MediaRequestHTTPError(
                f"provider request failed: {normalized_method} {url}",
            ) from exc

        if not response_payload:
            return None

        try:
            text = response_payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MediaRequestHTTPError(
                f"provider returned non-UTF-8 content: "
                f"{normalized_method} {url}",
            ) from exc

        try:
            return loads(text)
        except JSONDecodeError as exc:
            raise MediaRequestHTTPError(
                f"provider returned invalid JSON: {normalized_method} {url}",
            ) from exc


def _normalize_base_url(value: object) -> str:
    normalized = _required_text(value, "base_url").rstrip("/")
    parsed = urlparse(normalized)

    if parsed.scheme not in {"http", "https"}:
        raise MediaRequestHTTPError("base_url must use http or https")
    if not parsed.netloc:
        raise MediaRequestHTTPError("base_url must include a host")
    if parsed.query or parsed.fragment:
        raise MediaRequestHTTPError(
            "base_url must not include a query or fragment",
        )
    if parsed.username or parsed.password:
        raise MediaRequestHTTPError("base_url must not contain credentials")

    return normalized


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MediaRequestHTTPError(f"{field_name} is required")
    return value.strip()


def _normalize_method(value: object) -> str:
    normalized = _required_text(value, "method").upper()
    if normalized not in {"GET", "POST", "DELETE"}:
        raise MediaRequestHTTPError(
            f"unsupported provider HTTP method: {normalized}",
        )
    return normalized
