from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest

from atlas.media.jellyfin_admin import (
    JellyfinAdminClient,
    JellyfinAdminError,
    JellyfinScheduledTaskConflictError,
    JellyfinScheduledTaskNotFoundError,
)


class Response:
    def __init__(
        self,
        value: object = b"",
    ) -> None:
        if isinstance(value, bytes):
            self.value = value
        else:
            self.value = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self.value


def client(opener) -> JellyfinAdminClient:
    return JellyfinAdminClient(
        "http://jellyfin:8096",
        "secret",
        opener=opener,
    )


def task(
    *,
    task_id: str = "task-1",
    key: str = "RefreshGuide",
    name: str = "Refresh Guide",
    state: str = "Idle",
) -> dict[str, str]:
    return {
        "Id": task_id,
        "Key": key,
        "Name": name,
        "State": state,
    }


def test_lists_only_safe_normalized_task_identity() -> None:
    observed = []

    def opener(request, *, timeout):
        observed.append((request, timeout))
        return Response(
            [
                {
                    **task(),
                    "Description": "secret-ish metadata",
                    "Triggers": [{"Type": "DailyTrigger"}],
                }
            ]
        )

    tasks = client(opener).list_scheduled_tasks()

    assert tuple(
        item.safe_dict()
        for item in tasks
    ) == (
        {
            "task_id": "task-1",
            "key": "RefreshGuide",
            "name": "Refresh Guide",
            "state": "Idle",
        },
    )

    request, timeout = observed[0]

    assert request.method == "GET"
    assert (
        request.full_url
        == "http://jellyfin:8096/ScheduledTasks"
    )
    assert timeout == 10.0

    headers = {
        str(key).lower(): value
        for key, value in request.header_items()
    }

    assert 'Token="secret"' in headers["authorization"]
    assert "x-emby-token" not in headers


def test_exact_task_key_resolution() -> None:
    def opener(_request, *, timeout):
        assert timeout == 10.0
        return Response(
            [
                task(
                    task_id="channels",
                    key="RefreshInternetChannels",
                    name="Refresh Channels",
                ),
                task(),
            ]
        )

    resolved = client(
        opener
    ).find_scheduled_task_by_key(
        "RefreshGuide"
    )

    assert resolved.task_id == "task-1"
    assert resolved.key == "RefreshGuide"


def test_task_key_match_is_exact() -> None:
    def opener(_request, *, timeout):
        assert timeout == 10.0
        return Response([task()])

    with pytest.raises(
        JellyfinScheduledTaskNotFoundError,
    ):
        client(
            opener
        ).find_scheduled_task_by_key(
            "refreshguide"
        )


def test_duplicate_exact_task_key_fails_closed() -> None:
    def opener(_request, *, timeout):
        assert timeout == 10.0
        return Response(
            [
                task(task_id="one"),
                task(task_id="two"),
            ]
        )

    with pytest.raises(
        JellyfinScheduledTaskConflictError,
        match="not unique",
    ):
        client(
            opener
        ).find_scheduled_task_by_key(
            "RefreshGuide"
        )


def test_duplicate_task_ids_fail_closed_case_insensitively() -> None:
    def opener(_request, *, timeout):
        assert timeout == 10.0
        return Response(
            [
                task(
                    task_id="ABC",
                    key="One",
                    name="One",
                ),
                task(
                    task_id="abc",
                    key="Two",
                    name="Two",
                ),
            ]
        )

    with pytest.raises(
        JellyfinAdminError,
        match="duplicate scheduled task IDs",
    ):
        client(opener).list_scheduled_tasks()


def test_get_scheduled_task_requires_matching_id() -> None:
    observed = []

    def opener(request, *, timeout):
        observed.append((request, timeout))
        return Response(
            task(task_id="different")
        )

    with pytest.raises(
        JellyfinAdminError,
        match="mismatched",
    ):
        client(opener).get_scheduled_task(
            "task-1"
        )

    request, _timeout = observed[0]

    assert request.method == "GET"
    assert (
        request.full_url
        == "http://jellyfin:8096/ScheduledTasks/task-1"
    )


def test_start_scheduled_task_posts_exact_id_without_body() -> None:
    observed = []

    def opener(request, *, timeout):
        observed.append((request, timeout))
        return Response()

    client(opener).start_scheduled_task(
        "task/one"
    )

    request, timeout = observed[0]

    assert request.method == "POST"
    assert (
        request.full_url
        == (
            "http://jellyfin:8096"
            "/ScheduledTasks/Running/task%2Fone"
        )
    )
    assert request.data is None
    assert timeout == 10.0


def test_404_is_normalized_to_task_not_found() -> None:
    def opener(request, *, timeout):
        assert timeout == 10.0
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            io.BytesIO(),
        )

    with pytest.raises(
        JellyfinScheduledTaskNotFoundError,
    ) as exc:
        client(opener).get_scheduled_task(
            "missing"
        )

    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    "payload",
    (
        {},
        ["not-an-object"],
        [
            {
                "Id": "task-1",
                "Key": "",
                "Name": "Refresh Guide",
                "State": "Idle",
            }
        ],
    ),
)
def test_rejects_malformed_task_inventory(
    payload,
) -> None:
    def opener(_request, *, timeout):
        assert timeout == 10.0
        return Response(payload)

    with pytest.raises(
        JellyfinAdminError,
    ):
        client(opener).list_scheduled_tasks()


def test_rejects_invalid_constructor_arguments() -> None:
    with pytest.raises(ValueError):
        JellyfinAdminClient(
            "",
            "secret",
        )

    with pytest.raises(ValueError):
        JellyfinAdminClient(
            "http://jellyfin:8096",
            "",
        )

    with pytest.raises(ValueError):
        JellyfinAdminClient(
            "http://jellyfin:8096",
            "secret",
            timeout_seconds=0,
        )
