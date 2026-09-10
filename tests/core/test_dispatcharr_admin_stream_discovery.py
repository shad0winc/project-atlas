from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "sports"
    / "src"
    / "dispatcharr_admin.py"
)


def _module():
    spec = importlib.util.spec_from_file_location(
        "dispatcharr_admin_stream_discovery_test",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    # dataclasses expects the executing module to exist in sys.modules.
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def _client(module):
    return module.DispatcharrAdminClient(
        base_url="http://dispatcharr.test",
        admin_username="admin",
        admin_password="secret",
    )


def test_safe_stream_mapping_exposes_only_resolution_fields() -> None:
    module = _module()

    stream = module.DispatcharrAdminClient._safe_stream(
        {
            "id": 175,
            "name": "US| NFL: PATRIOTS HD",
            "url": "http://provider.invalid/secret",
            "m3u_account": 2,
            "channel_group": 10,
            "is_stale": False,
            "stream_id": 999999,
        },
        expected_account_id=2,
        group_names={
            10: "AM | USA NFL",
        },
    )

    assert stream.to_mapping() == {
        "stream_id": 175,
        "name": "US| NFL: PATRIOTS HD",
        "m3u_account_id": 2,
        "group_name": "AM | USA NFL",
        "is_stale": False,
    }

    rendered = repr(
        stream.to_mapping()
    ).casefold()

    assert "provider.invalid" not in rendered
    assert "url" not in rendered
    assert "password" not in rendered
    assert "username" not in rendered
    assert "token" not in rendered
    assert "999999" not in rendered


def test_safe_stream_uses_dispatcharr_pk_not_provider_stream_id() -> None:
    module = _module()

    stream = module.DispatcharrAdminClient._safe_stream(
        {
            "id": 181,
            "name": "US| NFL: SEAHAWKS HD",
            "m3u_account": 2,
            "channel_group": 10,
            "is_stale": False,
            "stream_id": 5001,
        },
        expected_account_id=2,
        group_names={
            10: "AM | USA NFL",
        },
    )

    assert stream.stream_id == 181
    assert stream.stream_id != 5001


def test_list_streams_is_account_scoped_and_resolves_group_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_access_token",
        lambda: "token-value",
    )

    calls: list[
        tuple[str, str, str | None]
    ] = []

    def fake_json_request(
        method: str,
        path: str,
        payload: Any = None,
        *,
        access_token: str | None = None,
    ) -> Any:
        del payload

        calls.append(
            (
                method,
                path,
                access_token,
            )
        )

        if path.startswith(
            "/api/channels/groups/"
        ):
            return {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": 10,
                        "name": "AM | USA NFL",
                    }
                ],
            }

        if path.startswith(
            "/api/channels/streams/"
        ):
            return {
                "count": 2,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": 175,
                        "name": (
                            "US| NFL: PATRIOTS HD"
                        ),
                        "url": (
                            "http://provider.invalid/a"
                        ),
                        "m3u_account": 2,
                        "channel_group": 10,
                        "is_stale": False,
                        "stream_id": 7001,
                    },
                    {
                        "id": 181,
                        "name": (
                            "US| NFL: SEAHAWKS HD"
                        ),
                        "url": (
                            "http://provider.invalid/b"
                        ),
                        "m3u_account": 2,
                        "channel_group": 10,
                        "is_stale": False,
                        "stream_id": 7002,
                    },
                ],
            }

        raise AssertionError(
            f"unexpected request path: {path}"
        )

    monkeypatch.setattr(
        client,
        "_json_request",
        fake_json_request,
    )

    streams = client.list_streams(
        account_id=2
    )

    assert [
        item.to_mapping()
        for item in streams
    ] == [
        {
            "stream_id": 175,
            "name": "US| NFL: PATRIOTS HD",
            "m3u_account_id": 2,
            "group_name": "AM | USA NFL",
            "is_stale": False,
        },
        {
            "stream_id": 181,
            "name": "US| NFL: SEAHAWKS HD",
            "m3u_account_id": 2,
            "group_name": "AM | USA NFL",
            "is_stale": False,
        },
    ]

    stream_calls = [
        path
        for method, path, token in calls
        if path.startswith(
            "/api/channels/streams/"
        )
    ]

    assert len(stream_calls) == 1
    assert "m3u_account=2" in stream_calls[0]

    assert all(
        method == "GET"
        for method, _, _ in calls
    )

    assert all(
        token == "token-value"
        for _, _, token in calls
    )


def test_paginated_get_reads_all_pages_without_following_next_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    paths: list[str] = []

    def fake_json_request(
        method: str,
        path: str,
        payload: Any = None,
        *,
        access_token: str | None = None,
    ) -> Any:
        del method
        del payload
        del access_token

        paths.append(path)

        if "page=1" in path:
            return {
                "results": [
                    {"id": 1},
                ],
                "next": (
                    "http://dispatcharr.internal/"
                    "api/channels/streams/?page=2"
                ),
            }

        if "page=2" in path:
            return {
                "results": [
                    {"id": 2},
                ],
                "next": None,
            }

        raise AssertionError(path)

    monkeypatch.setattr(
        client,
        "_json_request",
        fake_json_request,
    )

    rows = client._paginated_get(
        "/api/channels/streams/?m3u_account=2",
        access_token="token",
        page_size=10000,
    )

    assert [
        row["id"]
        for row in rows
    ] == [1, 2]

    assert len(paths) == 2

    assert all(
        path.startswith(
            "/api/channels/streams/"
        )
        for path in paths
    )

    assert not any(
        "dispatcharr.internal" in path
        for path in paths
    )


def test_paginated_get_accepts_bare_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *args, **kwargs: [
            {
                "id": 10,
                "name": "NFL",
            }
        ],
    )

    rows = client._paginated_get(
        "/api/channels/groups/",
        access_token="token",
    )

    assert rows == (
        {
            "id": 10,
            "name": "NFL",
        },
    )


def test_stream_for_wrong_account_fails_closed() -> None:
    module = _module()

    with pytest.raises(
        module.DispatcharrAdminError,
        match="wrong account",
    ):
        module.DispatcharrAdminClient._safe_stream(
            {
                "id": 175,
                "name": "NFL",
                "m3u_account": 3,
                "channel_group": 10,
            },
            expected_account_id=2,
            group_names={
                10: "NFL",
            },
        )


def test_unknown_channel_group_fails_closed() -> None:
    module = _module()

    with pytest.raises(
        module.DispatcharrAdminError,
        match="unknown channel group",
    ):
        module.DispatcharrAdminClient._safe_stream(
            {
                "id": 175,
                "name": "NFL",
                "m3u_account": 2,
                "channel_group": 99,
            },
            expected_account_id=2,
            group_names={
                10: "NFL",
            },
        )


def test_duplicate_stream_ids_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_access_token",
        lambda: "token",
    )

    monkeypatch.setattr(
        client,
        "_group_names",
        lambda **kwargs: {
            10: "NFL",
        },
    )

    monkeypatch.setattr(
        client,
        "_paginated_get",
        lambda *args, **kwargs: (
            {
                "id": 175,
                "name": "A",
                "m3u_account": 2,
                "channel_group": 10,
            },
            {
                "id": 175,
                "name": "B",
                "m3u_account": 2,
                "channel_group": 10,
            },
        ),
    )

    with pytest.raises(
        module.DispatcharrAdminError,
        match="duplicate stream identifiers",
    ):
        client.list_streams(
            account_id=2
        )


@pytest.mark.parametrize(
    "account_id",
    (
        0,
        -1,
        True,
        "invalid",
    ),
)
def test_list_streams_rejects_invalid_account_identifier(
    account_id: object,
) -> None:
    module = _module()
    client = _client(module)

    with pytest.raises(
        module.DispatcharrAdminError,
        match="account identifier is invalid",
    ):
        client.list_streams(
            account_id=account_id,  # type: ignore[arg-type]
        )
