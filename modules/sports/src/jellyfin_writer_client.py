from __future__ import annotations

from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


REFRESH_PATH = (
    "/internal/v1/jellyfin/live-tv/refresh"
)
INVENTORY_PATH = (
    "/internal/v1/jellyfin/live-tv/channels"
)
EXPECTED_TASK_KEY = "RefreshGuide"

DEFAULT_BASE_URL = (
    "http://atlas-jellyfin-writer:8004"
)
DEFAULT_TIMEOUT_SECONDS = 75.0


@dataclass(frozen=True, slots=True)
class JellyfinLiveTvChannel:
    item_id: str
    channel_number: str | None


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

    def list_live_tv_channels(
        self,
    ) -> tuple[JellyfinLiveTvChannel, ...]:
        request = urllib.request.Request(
            self._base_url + INVENTORY_PATH,
            headers={
                "Accept": "application/json",
                "Authorization": (
                    f"Bearer {self._token}"
                ),
            },
            method="GET",
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
            or set(payload) != {"channels"}
            or not isinstance(
                payload["channels"],
                list,
            )
        ):
            raise JellyfinWriterClientError(
                "Jellyfin writer returned an invalid "
                "Live TV inventory."
            )

        channels: list[
            JellyfinLiveTvChannel
        ] = []
        seen_item_ids: set[str] = set()

        for entry in payload["channels"]:
            if (
                not isinstance(entry, dict)
                or set(entry)
                != {
                    "item_id",
                    "channel_number",
                }
            ):
                raise JellyfinWriterClientError(
                    "Jellyfin writer returned an invalid "
                    "Live TV inventory."
                )

            item_id = entry.get(
                "item_id"
            )
            channel_number = entry.get(
                "channel_number"
            )

            if not isinstance(
                item_id,
                str,
            ):
                raise JellyfinWriterClientError(
                    "Jellyfin writer returned an invalid "
                    "Live TV inventory."
                )

            item_id = item_id.strip()

            if not item_id:
                raise JellyfinWriterClientError(
                    "Jellyfin writer returned an invalid "
                    "Live TV inventory."
                )

            if channel_number is not None:
                if not isinstance(
                    channel_number,
                    str,
                ):
                    raise JellyfinWriterClientError(
                        "Jellyfin writer returned an invalid "
                        "Live TV inventory."
                    )

                channel_number = (
                    channel_number.strip()
                )

                if not channel_number:
                    raise JellyfinWriterClientError(
                        "Jellyfin writer returned an invalid "
                        "Live TV inventory."
                    )

            normalized_item_id = (
                item_id.casefold()
            )

            if (
                normalized_item_id
                in seen_item_ids
            ):
                raise JellyfinWriterClientError(
                    "Jellyfin writer returned duplicate "
                    "Live TV item identity."
                )

            seen_item_ids.add(
                normalized_item_id
            )

            channels.append(
                JellyfinLiveTvChannel(
                    item_id=item_id,
                    channel_number=channel_number,
                )
            )

        return tuple(
            channels
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
