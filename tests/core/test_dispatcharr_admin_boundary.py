from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "modules"
    / "sports"
    / "src"
    / "dispatcharr_admin.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "atlas_test_dispatcharr_admin",
        MODULE_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[spec.name] = module

    spec.loader.exec_module(
        module
    )

    return module


def test_safe_account_mapping_never_returns_credentials() -> None:
    module = _load_module()

    account = module.DispatcharrAdminClient._safe_account(
        {
            "id": 2,
            "name": "Provider Account",
            "account_type": "XC",
            "is_active": False,
            "max_streams": 1,
            "server_url": "https://provider.invalid",
            "username": "hidden-user",
            "password": "hidden-password",
        }
    )

    payload = account.to_mapping()

    assert payload[
        "credentials_configured"
    ] is True

    serialized = repr(
        payload
    ).lower()

    assert "hidden-user" not in serialized
    assert "hidden-password" not in serialized
    assert "server_url" not in payload
    assert "username" not in payload
    assert "password" not in payload


def test_blank_password_is_not_sent_on_update(
    monkeypatch,
) -> None:
    module = _load_module()

    client = module.DispatcharrAdminClient(
        base_url="http://dispatcharr.invalid",
        admin_username="admin",
        admin_password="admin-secret",
    )

    monkeypatch.setattr(
        client,
        "_raw_account",
        lambda _account_id: {
            "id": 2,
            "name": "Provider Account",
            "account_type": "XC",
            "is_active": False,
            "max_streams": 1,
            "username": "existing",
            "password": "existing-secret",
        },
    )

    monkeypatch.setattr(
        client,
        "_access_token",
        lambda: "opaque-token",
    )

    seen = {}

    def request(
        method,
        path,
        payload=None,
        *,
        access_token=None,
    ):
        seen["method"] = method
        seen["path"] = path
        seen["payload"] = payload
        seen["access_token"] = (
            access_token
        )

        return {
            "id": 2,
            "name": "Provider Account",
            "account_type": "XC",
            "is_active": False,
            "max_streams": 1,
            "username": "changed",
            "password": "existing-secret",
        }

    monkeypatch.setattr(
        client,
        "_json_request",
        request,
    )

    client.update_credentials(
        account_id=2,
        username="changed",
        password="",
    )

    assert seen["payload"] == {
        "username": "changed",
    }

    assert (
        "password"
        not in seen["payload"]
    )


@pytest.mark.parametrize(
    "url",
    (
        "",
        "ftp://example.test",
        "https://user:pass@example.test",
    ),
)
def test_unsafe_server_urls_are_rejected(
    monkeypatch,
    url,
) -> None:
    module = _load_module()

    client = module.DispatcharrAdminClient(
        base_url="http://dispatcharr.invalid",
        admin_username="admin",
        admin_password="admin-secret",
    )

    monkeypatch.setattr(
        client,
        "_raw_account",
        lambda _account_id: {
            "id": 2,
            "name": "Provider Account",
            "account_type": "XC",
            "is_active": False,
            "max_streams": 1,
            "username": "existing",
            "password": "existing-secret",
        },
    )

    with pytest.raises(
        module.DispatcharrAdminError
    ):
        client.update_credentials(
            account_id=2,
            server_url=url,
        )


def test_connection_result_is_secret_safe() -> None:
    module = _load_module()

    result = module.SafeConnectionTest(
        ok=True,
        status="Active",
        expires_at="example-expiration",
        provider_max_connections=1,
        active_connections=0,
    )

    payload = result.to_mapping()

    serialized = repr(
        payload
    ).lower()

    for forbidden in (
        "password",
        "username",
        "server_url",
        "token",
        "api_key",
    ):
        assert forbidden not in serialized


def test_connection_does_not_depend_on_dispatcharr_python_modules() -> None:
    text = MODULE_PATH.read_text(
        encoding="utf-8"
    )

    assert "core.xtream_codes" not in text
    assert "player_api.php" in text


def test_connection_parses_only_safe_provider_status(
    monkeypatch,
) -> None:
    module = _load_module()

    client = module.DispatcharrAdminClient(
        base_url="http://dispatcharr.invalid",
        admin_username="admin",
        admin_password="admin-secret",
    )

    monkeypatch.setattr(
        client,
        "_raw_account",
        lambda _account_id: {
            "id": 2,
            "name": "Provider Account",
            "account_type": "XC",
            "is_active": False,
            "max_streams": 1,
            "server_url": (
                "https://provider.example"
            ),
            "username": "provider-user",
            "password": "provider-secret",
        },
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc,
            traceback,
        ):
            return False

        def read(self):
            return (
                b'{"user_info":{'
                b'"status":"Active",'
                b'"exp_date":"1234567890",'
                b'"max_connections":"3",'
                b'"active_cons":"1",'
                b'"username":"provider-user",'
                b'"password":"provider-secret"'
                b'}}'
            )

    seen = {}

    def urlopen(
        request,
        *,
        timeout,
    ):
        seen["url"] = (
            request.full_url
        )
        seen["timeout"] = timeout

        return Response()

    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        urlopen,
    )

    result = client.test_connection(
        account_id=2
    ).to_mapping()

    assert result == {
        "ok": True,
        "status": "Active",
        "expires_at": "1234567890",
        "provider_max_connections": 3,
        "active_connections": 1,
    }

    serialized = repr(
        result
    )

    assert "provider-user" not in serialized
    assert "provider-secret" not in serialized

    # Test-only assertion: credentials necessarily
    # exist in the upstream protocol request, but not
    # in the returned Atlas result.
    assert "player_api.php" in seen["url"]


def test_provider_request_error_never_contains_credential_url(
    monkeypatch,
) -> None:
    module = _load_module()

    client = module.DispatcharrAdminClient(
        base_url="http://dispatcharr.invalid",
        admin_username="admin",
        admin_password="admin-secret",
    )

    monkeypatch.setattr(
        client,
        "_raw_account",
        lambda _account_id: {
            "id": 2,
            "name": "Provider Account",
            "account_type": "XC",
            "is_active": False,
            "max_streams": 1,
            "server_url": (
                "https://provider.example"
            ),
            "username": "provider-user",
            "password": "provider-secret",
        },
    )

    def fail(
        request,
        *,
        timeout,
    ):
        raise module.urllib.error.URLError(
            "network failure"
        )

    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        fail,
    )

    with pytest.raises(
        module.DispatcharrAdminError
    ) as captured:
        client.test_connection(
            account_id=2
        )

    message = str(
        captured.value
    )

    assert "provider-user" not in message
    assert "provider-secret" not in message
    assert "player_api.php" not in message


def test_writer_packages_dispatcharr_admin_module_and_private_network() -> None:
    dockerfile = (
        ROOT
        / "modules"
        / "sports"
        / "Dockerfile.private-api"
    ).read_text(
        encoding="utf-8"
    )

    ingress = (
        ROOT
        / "stack"
        / "ingress.yml"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "dispatcharr_admin.py "
        "/srv/sports/dispatcharr_admin.py"
        in dockerfile
    )

    sports_writer = ingress.split(
        "  sports-writer:\n",
        1,
    )[1].split(
        "\n  identity-writer:",
        1,
    )[0]

    assert (
        "      - atlas-identity\n"
        in sports_writer
    )
    assert (
        "      - atlas\n"
        in sports_writer
    )

    assert (
        "DISPATCHARR_INTERNAL_URL:"
        in sports_writer
    )
    assert (
        "DISPATCHARR_ADMIN_USERNAME:"
        in sports_writer
    )
    assert (
        "DISPATCHARR_ADMIN_PASSWORD:"
        in sports_writer
    )
