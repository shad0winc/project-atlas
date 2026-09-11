"""Narrow privileged Jellyfin scheduled-task administration.

This module defines the HTTP contract only. It does not read runtime
credentials, choose an owning service, or execute tasks automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from atlas.media.jellyfin_auth import (
    build_jellyfin_authorization,
)


RequestOpener = Callable[..., Any]


class JellyfinAdminError(RuntimeError):
    """Base failure for Jellyfin administrative operations."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class JellyfinScheduledTaskNotFoundError(
    JellyfinAdminError
):
    """Requested Jellyfin scheduled task does not exist."""


class JellyfinScheduledTaskConflictError(
    JellyfinAdminError
):
    """Scheduled-task identity was not unique."""


@dataclass(frozen=True, slots=True)
class JellyfinScheduledTask:
    """Safe Jellyfin scheduled-task identity/state."""

    task_id: str
    key: str
    name: str
    state: str

    def safe_dict(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "key": self.key,
            "name": self.name,
            "state": self.state,
        }


class JellyfinAdminClient:
    """Perform narrow Jellyfin scheduled-task administration."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 10.0,
        opener: RequestOpener = urlopen,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        normalized_key = api_key.strip()

        if not normalized_url:
            raise ValueError(
                "Jellyfin base URL is required."
            )

        if not normalized_key:
            raise ValueError(
                "Jellyfin API key is required."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Jellyfin timeout must be greater than zero."
            )

        self._base_url = normalized_url
        self._api_key = normalized_key
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    @staticmethod
    def _required_string(
        value: object,
        field: str,
    ) -> str:
        if not isinstance(value, str):
            raise JellyfinAdminError(
                f"{field} must be a string."
            )

        normalized = value.strip()

        if not normalized:
            raise JellyfinAdminError(
                f"{field} is required."
            )

        return normalized

    @classmethod
    def _normalize_task(
        cls,
        value: object,
    ) -> JellyfinScheduledTask:
        if not isinstance(value, dict):
            raise JellyfinAdminError(
                "Jellyfin returned an invalid scheduled task."
            )

        return JellyfinScheduledTask(
            task_id=cls._required_string(
                value.get("Id"),
                "Jellyfin scheduled task ID",
            ),
            key=cls._required_string(
                value.get("Key"),
                "Jellyfin scheduled task key",
            ),
            name=cls._required_string(
                value.get("Name"),
                "Jellyfin scheduled task name",
            ),
            state=cls._required_string(
                value.get("State"),
                "Jellyfin scheduled task state",
            ),
        )

    def list_scheduled_tasks(
        self,
    ) -> tuple[JellyfinScheduledTask, ...]:
        """Return normalized scheduled-task identities/state."""

        raw = self._request(
            "GET",
            "/ScheduledTasks",
        )

        try:
            payload = json.loads(
                raw.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise JellyfinAdminError(
                "Jellyfin returned an invalid scheduled-task response."
            ) from exc

        if not isinstance(payload, list):
            raise JellyfinAdminError(
                "Jellyfin returned an invalid scheduled-task response."
            )

        tasks = tuple(
            self._normalize_task(entry)
            for entry in payload
        )

        seen_ids: set[str] = set()

        for task in tasks:
            normalized_id = task.task_id.casefold()

            if normalized_id in seen_ids:
                raise JellyfinAdminError(
                    "Jellyfin returned duplicate scheduled task IDs."
                )

            seen_ids.add(normalized_id)

        return tasks

    def get_scheduled_task(
        self,
        task_id: str,
    ) -> JellyfinScheduledTask:
        """Return one exact scheduled task by Jellyfin task ID."""

        normalized_id = self._required_string(
            task_id,
            "Jellyfin scheduled task ID",
        )

        raw = self._request(
            "GET",
            (
                "/ScheduledTasks/"
                + quote(normalized_id, safe="")
            ),
        )

        try:
            payload = json.loads(
                raw.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise JellyfinAdminError(
                "Jellyfin returned an invalid scheduled-task response."
            ) from exc

        task = self._normalize_task(payload)

        if task.task_id.casefold() != normalized_id.casefold():
            raise JellyfinAdminError(
                "Jellyfin returned a mismatched scheduled task."
            )

        return task

    def find_scheduled_task_by_key(
        self,
        key: str,
    ) -> JellyfinScheduledTask:
        """Resolve exactly one scheduled task by exact Jellyfin key."""

        normalized_key = self._required_string(
            key,
            "Jellyfin scheduled task key",
        )

        matches = tuple(
            task
            for task in self.list_scheduled_tasks()
            if task.key == normalized_key
        )

        if not matches:
            raise JellyfinScheduledTaskNotFoundError(
                "Jellyfin scheduled task was not found.",
                status_code=404,
            )

        if len(matches) != 1:
            raise JellyfinScheduledTaskConflictError(
                "Jellyfin scheduled task key is not unique.",
                status_code=409,
            )

        return matches[0]

    def start_scheduled_task(
        self,
        task_id: str,
    ) -> None:
        """Start one exact Jellyfin scheduled task by ID."""

        normalized_id = self._required_string(
            task_id,
            "Jellyfin scheduled task ID",
        )

        self._request(
            "POST",
            (
                "/ScheduledTasks/Running/"
                + quote(normalized_id, safe="")
            ),
        )

    def _request(
        self,
        method: str,
        path: str,
    ) -> bytes:
        request = Request(
            f"{self._base_url}{path}",
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization":
                    build_jellyfin_authorization(
                        token=self._api_key,
                    ),
            },
        )

        try:
            with self._opener(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code == 404:
                raise JellyfinScheduledTaskNotFoundError(
                    "Jellyfin scheduled task was not found.",
                    status_code=404,
                ) from exc

            raise JellyfinAdminError(
                "Jellyfin scheduled-task request failed.",
                status_code=exc.code,
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise JellyfinAdminError(
                "Jellyfin scheduled-task request failed."
            ) from exc
