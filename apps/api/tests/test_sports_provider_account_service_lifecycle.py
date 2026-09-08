from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from atlas_api.services.sports import (
    SportsProviderAccountConflictError,
    SportsProviderAccountInvalidError,
    SportsProviderAccountNotFoundError,
    SportsWriterBackedAPIService,
    SportsWriterTransportError,
)


def _service():
    return SportsWriterBackedAPIService(
        base_url="http://writer.test",
        token="test-token",
    )


def _created_payload():
    return {
        "source": {
            "source_id": "source one",
            "display_name": "Primary",
            "provider_id": "provider-a",
            "provider_display_name": (
                "Provider A"
            ),
            "account_display_name": (
                "Primary"
            ),
            "kind": (
                "licensed_subscription"
            ),
            "enabled": False,
            "priority": 120,
            "max_connections": 4,
            "backend_reference": (
                "dispatcharr:m3u:42"
            ),
        },
        "account": {
            "account_id": 42,
            "name": "source one",
            "account_type": "XC",
            "enabled": True,
            "configured_max_connections": 4,
            "credentials_configured": True,
        },
    }


def test_create_provider_account_uses_exact_private_transaction(
    monkeypatch,
) -> None:
    service = _service()
    calls = []

    def request(
        method,
        path,
        body=None,
    ):
        calls.append(
            (
                method,
                path,
                body,
            )
        )

        if method == "POST":
            return _created_payload()

        assert method == "GET"
        assert path == (
            "/internal/v1/sources"
        )

        return {
            "providers": [],
            "sources": [],
        }

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    result = service.create_provider_account(
        source_id=" source one ",
        provider_id=" provider-a ",
        provider_display_name=" Provider A ",
        account_display_name=" Primary ",
        server_url=(
            " https://provider.example "
        ),
        username=" account-user ",
        password="account-secret",
        max_connections=4,
        priority=120,
    )

    assert result == {
        "providers": [],
        "sources": [],
    }

    assert calls == [
        (
            "POST",
            "/internal/v1/provider-accounts",
            {
                "source_id": "source one",
                "provider_id": "provider-a",
                "provider_display_name": (
                    "Provider A"
                ),
                "account_display_name": (
                    "Primary"
                ),
                "server_url": (
                    "https://provider.example"
                ),
                "username": "account-user",
                "password": "account-secret",
                "max_connections": 4,
                "priority": 120,
            },
        ),
        (
            "GET",
            "/internal/v1/sources",
            None,
        ),
    ]


def test_create_provider_account_rejects_secret_bearing_source(
    monkeypatch,
) -> None:
    service = _service()

    payload = _created_payload()
    payload["source"][
        "username"
    ] = "must-not-pass"

    monkeypatch.setattr(
        service,
        "_request",
        lambda *_args, **_kwargs: payload,
    )

    with pytest.raises(
        SportsWriterTransportError
    ):
        service.create_provider_account(
            source_id="source-one",
            provider_id="provider-a",
            provider_display_name=(
                "Provider A"
            ),
            account_display_name="Primary",
            server_url=(
                "https://provider.example"
            ),
            username="account-user",
            password="account-secret",
            max_connections=4,
        )


def test_create_provider_account_rejects_unsafe_account_shape(
    monkeypatch,
) -> None:
    service = _service()

    payload = _created_payload()
    payload["account"][
        "password"
    ] = "must-not-pass"

    monkeypatch.setattr(
        service,
        "_request",
        lambda *_args, **_kwargs: payload,
    )

    with pytest.raises(
        SportsWriterTransportError
    ):
        service.create_provider_account(
            source_id="source-one",
            provider_id="provider-a",
            provider_display_name=(
                "Provider A"
            ),
            account_display_name="Primary",
            server_url=(
                "https://provider.example"
            ),
            username="account-user",
            password="account-secret",
            max_connections=4,
        )


def test_create_provider_account_rejects_invalid_capacity_before_transport(
    monkeypatch,
) -> None:
    service = _service()
    called = False

    def request(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError(
            "transport must not run"
        )

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    with pytest.raises(ValueError):
        service.create_provider_account(
            source_id="source-one",
            provider_id="provider-a",
            provider_display_name=(
                "Provider A"
            ),
            account_display_name="Primary",
            server_url=(
                "https://provider.example"
            ),
            username="account-user",
            password="account-secret",
            max_connections=0,
        )

    assert called is False


def test_remove_provider_account_uses_exact_private_route(
    monkeypatch,
) -> None:
    service = _service()
    calls = []

    def request(
        method,
        path,
        body=None,
    ):
        calls.append(
            (
                method,
                path,
                body,
            )
        )
        return {
            "removed": True,
            "source_id": "source one",
        }

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    assert (
        service.remove_provider_account(
            source_id=" source one "
        )
        is True
    )

    assert calls == [
        (
            "DELETE",
            (
                "/internal/v1/"
                "provider-accounts/"
                "source%20one"
            ),
            None,
        )
    ]


def test_remove_provider_account_rejects_unsafe_response(
    monkeypatch,
) -> None:
    service = _service()

    monkeypatch.setattr(
        service,
        "_request",
        lambda *_args, **_kwargs: {
            "removed": True,
            "source_id": "source-one",
            "backend_reference": (
                "dispatcharr:m3u:42"
            ),
        },
    )

    with pytest.raises(
        SportsWriterTransportError
    ):
        service.remove_provider_account(
            source_id="source-one"
        )


@pytest.mark.parametrize(
    (
        "code",
        "error_type",
    ),
    (
        (
            "sports_provider_account_"
            "playback_dependency",
            SportsProviderAccountConflictError,
        ),
        (
            "sports_source_not_found",
            SportsProviderAccountNotFoundError,
        ),
        (
            "sports_provider_account_invalid",
            SportsProviderAccountInvalidError,
        ),
    ),
)
def test_private_lifecycle_errors_preserve_public_semantics(
    monkeypatch,
    code,
    error_type,
) -> None:
    service = _service()

    body = json.dumps(
        {
            "code": code,
            "error": "controlled failure",
        }
    ).encode("utf-8")

    def urlopen(
        request,
        timeout,
    ):
        raise urllib.error.HTTPError(
            request.full_url,
            409,
            "Conflict",
            {},
            io.BytesIO(body),
        )

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        urlopen,
    )

    with pytest.raises(error_type):
        service.remove_provider_account(
            source_id="source-one"
        )
