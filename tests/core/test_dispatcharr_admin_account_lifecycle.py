from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "sports"
    / "src"
    / "dispatcharr_admin.py"
)


def _load_module():
    name = (
        "atlas_test_dispatcharr_admin_"
        "account_lifecycle"
    )

    spec = importlib.util.spec_from_file_location(
        name,
        MODULE_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[name] = module
    spec.loader.exec_module(module)

    return module


def _client(module):
    return object.__new__(
        module.DispatcharrAdminClient
    )


def test_create_account_uses_narrow_xc_payload(
    monkeypatch,
) -> None:
    module = _load_module()
    client = _client(module)

    calls = []
    safe_result = object()

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
        "_access_token",
        lambda self: "test-token",
    )

    def request(
        self,
        method,
        path,
        body,
        *,
        access_token,
    ):
        calls.append(
            (
                method,
                path,
                body,
                access_token,
            )
        )
        return {
            "id": 42,
            "password": "must-be-filtered",
        }

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
        "_json_request",
        request,
    )

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
        "_safe_account",
        staticmethod(
            lambda payload: (
                safe_result
                if payload["id"] == 42
                else None
            )
        ),
    )

    result = client.create_account(
        name=" XC4 Main ",
        server_url=(
            "https://provider.example"
        ),
        username=" xc4-user ",
        password="xc4-secret",
        max_connections=4,
    )

    assert result is safe_result

    assert calls == [
        (
            "POST",
            "/api/m3u/accounts/",
            {
                "name": "XC4 Main",
                "server_url": (
                    "https://provider.example"
                ),
                "account_type": "XC",
                "username": "xc4-user",
                "password": "xc4-secret",
                "max_streams": 4,
                "is_active": True,
                "enable_vod": False,
                "auto_enable_new_groups_live": (
                    False
                ),
                "auto_enable_new_groups_vod": (
                    False
                ),
                "auto_enable_new_groups_series": (
                    False
                ),
            },
            "test-token",
        )
    ]


@pytest.mark.parametrize(
    "server_url",
    (
        "",
        "ftp://provider.example",
        "https://user:pass@provider.example",
        "not-a-url",
    ),
)
def test_create_account_rejects_unsafe_server_url(
    monkeypatch,
    server_url,
) -> None:
    module = _load_module()
    client = _client(module)

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
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
        client.create_account(
            name="XC4 Main",
            server_url=server_url,
            username="xc4-user",
            password="xc4-secret",
            max_connections=4,
        )


@pytest.mark.parametrize(
    "max_connections",
    (
        0,
        1001,
        True,
    ),
)
def test_create_account_rejects_invalid_capacity(
    monkeypatch,
    max_connections,
) -> None:
    module = _load_module()
    client = _client(module)

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
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
        client.create_account(
            name="XC4 Main",
            server_url=(
                "https://provider.example"
            ),
            username="xc4-user",
            password="xc4-secret",
            max_connections=max_connections,
        )


def test_create_account_requires_password(
    monkeypatch,
) -> None:
    module = _load_module()
    client = _client(module)

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
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
        client.create_account(
            name="XC4 Main",
            server_url=(
                "https://provider.example"
            ),
            username="xc4-user",
            password="",
            max_connections=4,
        )


def test_delete_account_calls_only_account_endpoint(
    monkeypatch,
) -> None:
    module = _load_module()
    client = _client(module)

    calls = []

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
        "_access_token",
        lambda self: "test-token",
    )

    def request(
        self,
        method,
        path,
        body,
        *,
        access_token,
    ):
        calls.append(
            (
                method,
                path,
                body,
                access_token,
            )
        )
        return {
            "deleted_channels": 0,
        }

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
        "_json_request",
        request,
    )

    result = client.delete_account(
        account_id=42
    )

    assert result is None

    assert calls == [
        (
            "DELETE",
            "/api/m3u/accounts/42/",
            {},
            "test-token",
        )
    ]


@pytest.mark.parametrize(
    "account_id",
    (
        0,
        -1,
        True,
        "invalid",
    ),
)
def test_delete_account_rejects_invalid_identifier(
    monkeypatch,
    account_id,
) -> None:
    module = _load_module()
    client = _client(module)

    monkeypatch.setattr(
        module.DispatcharrAdminClient,
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
        client.delete_account(
            account_id=account_id
        )
