from __future__ import annotations

import importlib.util
import sys
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
        "dispatcharr_admin_channel_lifecycle_test",
        MODULE_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def _client(module):
    return module.DispatcharrAdminClient(
        base_url="http://dispatcharr.test",
        admin_username="admin",
        admin_password="secret",
    )


def _response(
    *,
    channel_id: int = 42,
    name: str = "Atlas Sports Event",
    streams: list[int] | None = None,
) -> dict[str, Any]:
    return {
        "id": channel_id,
        "uuid": (
            "00000000-0000-0000-0000-"
            "000000000042"
        ),
        "name": name,
        "streams": (
            [175, 181]
            if streams is None
            else streams
        ),
        # Dispatcharr may return many additional
        # fields. Safe mapping must discard them.
        "channel_number": 9000,
        "hidden_from_output": False,
        "source_stream": {
            "url": "http://provider.invalid/secret",
        },
        "override": {
            "password": "never-return-this",
        },
    }


def test_safe_channel_mapping_exposes_only_safe_identity() -> None:
    module = _module()

    channel = (
        module.DispatcharrAdminClient
        ._safe_channel(
            _response()
        )
    )

    assert channel.to_mapping() == {
        "channel_id": 42,
        "channel_uuid": (
            "00000000-0000-0000-0000-"
            "000000000042"
        ),
        "name": "Atlas Sports Event",
        "stream_ids": [
            175,
            181,
        ],
    }

    rendered = repr(
        channel.to_mapping()
    ).casefold()

    for forbidden in (
        "provider.invalid",
        "url",
        "password",
        "token",
        "override",
        "source_stream",
    ):
        assert forbidden not in rendered


def test_create_channel_uses_exact_shared_channel_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_access_token",
        lambda: "opaque-token",
    )

    calls: list[
        tuple[
            str,
            str,
            dict[str, Any],
            str | None,
        ]
    ] = []

    def request(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        access_token: str | None = None,
    ) -> Any:
        assert payload is not None

        calls.append(
            (
                method,
                path,
                payload,
                access_token,
            )
        )

        return _response(
            name="Seahawks vs Patriots",
            streams=[181, 175],
        )

    monkeypatch.setattr(
        client,
        "_json_request",
        request,
    )

    channel = client.create_channel(
        name="  Seahawks vs Patriots  ",
        stream_ids=(
            181,
            175,
        ),
    )

    assert channel.stream_ids == (
        181,
        175,
    )

    assert calls == [
        (
            "POST",
            "/api/channels/channels/",
            {
                "name": (
                    "Seahawks vs Patriots"
                ),
                "streams": [
                    181,
                    175,
                ],
                "channel_profile_ids": [
                    0,
                ],
            },
            "opaque-token",
        )
    ]


def test_update_channel_uses_patch_and_preserves_stream_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_access_token",
        lambda: "token",
    )

    calls = []

    def request(
        method,
        path,
        payload=None,
        *,
        access_token=None,
    ):
        calls.append(
            (
                method,
                path,
                payload,
                access_token,
            )
        )

        return _response(
            channel_id=42,
            name="Updated Event",
            streams=[
                302,
                301,
                202,
                201,
            ],
        )

    monkeypatch.setattr(
        client,
        "_json_request",
        request,
    )

    channel = client.update_channel(
        channel_id=42,
        name=" Updated Event ",
        stream_ids=(
            302,
            301,
            202,
            201,
        ),
    )

    assert channel.stream_ids == (
        302,
        301,
        202,
        201,
    )

    assert calls == [
        (
            "PATCH",
            "/api/channels/channels/42/",
            {
                "name": "Updated Event",
                "streams": [
                    302,
                    301,
                    202,
                    201,
                ],
            },
            "token",
        )
    ]


def test_update_channel_can_change_name_without_stream_rewrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_access_token",
        lambda: "token",
    )

    seen = {}

    def request(
        method,
        path,
        payload=None,
        *,
        access_token=None,
    ):
        seen.update(
            method=method,
            path=path,
            payload=payload,
            token=access_token,
        )

        return _response(
            name="Renamed",
        )

    monkeypatch.setattr(
        client,
        "_json_request",
        request,
    )

    client.update_channel(
        channel_id=42,
        name="Renamed",
    )

    assert seen["payload"] == {
        "name": "Renamed",
    }


def test_channel_404_is_translated_without_changing_account_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_access_token",
        lambda: "token",
    )

    def missing(*args, **kwargs):
        raise (
            module.DispatcharrAccountNotFoundError(
                "Dispatcharr account was not found."
            )
        )

    monkeypatch.setattr(
        client,
        "_json_request",
        missing,
    )

    with pytest.raises(
        module.DispatcharrChannelNotFoundError,
        match="channel was not found",
    ):
        client.update_channel(
            channel_id=42,
            name="Updated",
        )


@pytest.mark.parametrize(
    "stream_ids",
    (
        (),
        (0,),
        (-1,),
        (True,),
        ("invalid",),
        (175, 175),
    ),
)
def test_create_channel_rejects_invalid_stream_sets_without_request(
    monkeypatch: pytest.MonkeyPatch,
    stream_ids,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *args, **kwargs: (
            pytest.fail(
                "Dispatcharr must not be called"
            )
        ),
    )

    with pytest.raises(
        module.DispatcharrAdminError
    ):
        client.create_channel(
            name="Atlas Event",
            stream_ids=stream_ids,
        )


@pytest.mark.parametrize(
    "name",
    (
        "",
        "   ",
    ),
)
def test_create_channel_rejects_blank_name_without_request(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *args, **kwargs: (
            pytest.fail(
                "Dispatcharr must not be called"
            )
        ),
    )

    with pytest.raises(
        module.DispatcharrAdminError,
        match="name cannot be blank",
    ):
        client.create_channel(
            name=name,
            stream_ids=(175,),
        )


@pytest.mark.parametrize(
    "channel_id",
    (
        0,
        -1,
        True,
        "invalid",
    ),
)
def test_update_channel_rejects_invalid_channel_identifier_without_request(
    monkeypatch: pytest.MonkeyPatch,
    channel_id,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *args, **kwargs: (
            pytest.fail(
                "Dispatcharr must not be called"
            )
        ),
    )

    with pytest.raises(
        module.DispatcharrAdminError,
        match="channel identifier is invalid",
    ):
        client.update_channel(
            channel_id=channel_id,
            name="Updated",
        )


def test_update_channel_requires_field_without_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = _client(module)

    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *args, **kwargs: (
            pytest.fail(
                "Dispatcharr must not be called"
            )
        ),
    )

    with pytest.raises(
        module.DispatcharrAdminError,
        match="at least one field",
    ):
        client.update_channel(
            channel_id=42,
        )


@pytest.mark.parametrize(
    "payload",
    (
        None,
        {},
        {
            "id": 42,
            "uuid": "",
            "name": "Event",
            "streams": [175],
        },
        {
            "id": 42,
            "uuid": "uuid-value",
            "name": "",
            "streams": [175],
        },
        {
            "id": 42,
            "uuid": "uuid-value",
            "name": "Event",
            "streams": [],
        },
        {
            "id": 42,
            "uuid": "uuid-value",
            "name": "Event",
            "streams": [175, 175],
        },
    ),
)
def test_safe_channel_malformed_response_fails_closed(
    payload,
) -> None:
    module = _module()

    with pytest.raises(
        module.DispatcharrAdminError
    ):
        (
            module.DispatcharrAdminClient
            ._safe_channel(payload)
        )


def test_channel_symbols_are_publicly_exported() -> None:
    module = _module()

    assert (
        "DispatcharrChannelNotFoundError"
        in module.__all__
    )

    assert (
        "SafeDispatcharrChannel"
        in module.__all__
    )
