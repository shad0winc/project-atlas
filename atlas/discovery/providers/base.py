"""Shared HTTP foundations for concrete Discovery providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from json import JSONDecodeError, loads
from socket import timeout as SocketTimeout
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from atlas.discovery.models import DiscoveryError
from atlas.discovery.provider import DiscoveryProvider


class DiscoveryProviderError(DiscoveryError):
    """Raised when a concrete Discovery provider request fails."""


@dataclass(frozen=True)
class BaseDiscoveryProvider(DiscoveryProvider):
    """Shared read-only HTTP behavior for Discovery providers."""

    base_url: str
    api_key: str = field(repr=False)
    timeout: float = 10.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "base_url",
            _normalize_base_url(self.base_url),
        )
        object.__setattr__(
            self,
            "api_key",
            _required_text(
                self.api_key,
                "api_key",
            ),
        )

        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or self.timeout <= 0
        ):
            raise DiscoveryProviderError(
                "timeout must be a positive number",
            )

        object.__setattr__(
            self,
            "timeout",
            float(self.timeout),
        )

    def _build_url(self, path: str) -> str:
        """Return an absolute provider URL for one API path."""

        normalized_path = _required_text(
            path,
            "path",
        )

        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"

        return urljoin(
            f"{self.base_url}/",
            normalized_path.lstrip("/"),
        )

    def _headers(self) -> dict[str, str]:
        """Return common read-only provider request headers."""

        return {
            "Accept": "application/json",
            "User-Agent": "Project-Atlas/Discovery",
            "X-Api-Key": self.api_key,
        }

    def _get_json(self, path: str) -> Any:
        """Perform one GET request and decode its JSON response."""

        url = self._build_url(path)
        request = Request(
            url=url,
            headers=self._headers(),
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = response.read()
        except HTTPError as exc:
            raise DiscoveryProviderError(
                f"provider request failed with HTTP {exc.code}: {url}",
            ) from exc
        except (URLError, SocketTimeout, TimeoutError) as exc:
            raise DiscoveryProviderError(
                f"provider request could not connect: {url}",
            ) from exc
        except OSError as exc:
            raise DiscoveryProviderError(
                f"provider request failed: {url}",
            ) from exc

        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DiscoveryProviderError(
                f"provider returned non-UTF-8 content: {url}",
            ) from exc

        try:
            return loads(text)
        except JSONDecodeError as exc:
            raise DiscoveryProviderError(
                f"provider returned invalid JSON: {url}",
            ) from exc


def _normalize_base_url(value: object) -> str:
    normalized = _required_text(
        value,
        "base_url",
    ).rstrip("/")

    parsed = urlparse(normalized)

    if parsed.scheme not in {"http", "https"}:
        raise DiscoveryProviderError(
            "base_url must use http or https",
        )

    if not parsed.netloc:
        raise DiscoveryProviderError(
            "base_url must include a host",
        )

    if parsed.query or parsed.fragment:
        raise DiscoveryProviderError(
            "base_url must not include a query or fragment",
        )

    return normalized


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryProviderError(
            f"{field_name} is required",
        )

    return value.strip()
