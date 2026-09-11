from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


REFRESH_PATH = (
    "/internal/v1/jellyfin/live-tv/refresh"
)
EXPECTED_TASK_KEY = "RefreshGuide"

DEFAULT_BASE_URL = (
    "http://atlas-jellyfin-writer:8004"
)
DEFAULT_TIMEOUT_SECONDS = 75.0


class JellyfinWriterClientError(RuntimeError):
    """Private Jellyfin writer request failed safely."""


class JellyfinWriterClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        normalized_base_url = str(
            base_url
        ).strip().rstrip("/")

        normalized_token = str(
            token
        ).strip()

        try:
            normalized_timeout = float(
                timeout_seconds
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Jellyfin writer timeout must be numeric."
            ) from exc

        parsed = urllib.parse.urlsplit(
            normalized_base_url
        )

        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Jellyfin writer URL is invalid."
            )

        if (
            not normalized_token
            or normalized_token == "CHANGE_ME"
        ):
            raise ValueError(
                "Jellyfin writer token is required."
            )

        if normalized_timeout <= 0:
            raise ValueError(
                "Jellyfin writer timeout must be positive."
            )

        self._base_url = normalized_base_url
        self._token = normalized_token
        self._timeout_seconds = normalized_timeout
        self._opener = (
            opener
            if opener is not None
            else urllib.request.urlopen
        )

    @classmethod
    def from_environment(
        cls,
    ) -> "JellyfinWriterClient":
        raw_timeout = os.getenv(
            "ATLAS_JELLYFIN_WRITER_TIMEOUT_SECONDS",
            str(DEFAULT_TIMEOUT_SECONDS),
        )

        return cls(
            base_url=os.getenv(
                "ATLAS_JELLYFIN_WRITER_URL",
                DEFAULT_BASE_URL,
            ),
            token=os.getenv(
                "ATLAS_JELLYFIN_WRITER_TOKEN",
                "",
            ),
            timeout_seconds=float(
                raw_timeout
            ),
        )

    def refresh_live_tv(
        self,
    ) -> None:
        request = urllib.request.Request(
            self._base_url + REFRESH_PATH,
            headers={
                "Accept": "application/json",
                "Authorization": (
                    f"Bearer {self._token}"
                ),
            },
            method="POST",
        )

        try:
            with self._opener(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                raw = response.read()

        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                message = (
                    "Jellyfin writer authentication failed."
                )
            elif exc.code == 409:
                message = (
                    "Jellyfin Live TV refresh is already "
                    "running."
                )
            elif exc.code == 504:
                message = (
                    "Jellyfin Live TV refresh timed out."
                )
            else:
                message = (
                    "Jellyfin writer request failed."
                )

            raise JellyfinWriterClientError(
                message
            ) from exc

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
        ) as exc:
            raise JellyfinWriterClientError(
                "Jellyfin writer is unavailable."
            ) from exc

        try:
            payload = json.loads(
                raw.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise JellyfinWriterClientError(
                "Jellyfin writer returned invalid JSON."
            ) from exc

        if (
            not isinstance(payload, dict)
            or payload.get("status") != "completed"
            or payload.get("task_key")
            != EXPECTED_TASK_KEY
        ):
            raise JellyfinWriterClientError(
                "Jellyfin writer returned an invalid "
                "refresh result."
            )
