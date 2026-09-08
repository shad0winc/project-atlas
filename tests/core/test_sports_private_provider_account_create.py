from __future__ import annotations

import importlib.util
import json
import sys
import threading
import types
import urllib.error
import urllib.request
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPORTS_SRC = (
    ROOT
    / "modules"
    / "sports"
    / "src"
)
PRIVATE_API = (
    SPORTS_SRC
    / "private_api.py"
)


def _load_private_api(monkeypatch):
    sys.path.insert(
        0,
        str(SPORTS_SRC),
    )

    name = (
        "atlas_test_private_provider_"
        "account_create"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            name,
            PRIVATE_API,
        )
    )

    assert spec is not None
    assert spec.loader is not None

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    monkeypatch.setitem(
        sys.modules,
        name,
        module,
    )

    spec.loader.exec_module(module)

    return module


class FakeStore:
    def __init__(
        self,
        *,
        sources=(),
        fail_write=False,
    ):
        self.sources = tuple(sources)
        self.fail_write = fail_write
        self.writes = []

    def load(self):
        return self.sources

    def write(self, sources):
        values = tuple(sources)
        self.writes.append(values)

        if self.fail_write:
            raise OSError(
                "simulated state failure"
            )

        self.sources = values


class FakeAccount:
    account_id = 42

    def to_mapping(self):
        return {
            "account_id": 42,
            "name": "xc4-account",
            "account_type": "XC",
            "enabled": True,
            "configured_max_connections": 4,
            "credentials_configured": True,
        }


class FakeDispatcharrAdminError(
    RuntimeError
):
    pass


class FakeClient:
    def __init__(
        self,
        *,
        fail_delete=False,
    ):
        self.creates = []
        self.deletes = []
        self.fail_delete = fail_delete

    def create_account(
        self,
        **kwargs,
    ):
        self.creates.append(
            dict(kwargs)
        )
        return FakeAccount()

    def delete_account(
        self,
        *,
        account_id,
    ):
        self.deletes.append(
            account_id
        )

        if self.fail_delete:
            raise (
                FakeDispatcharrAdminError(
                    "simulated compensation "
                    "failure"
                )
            )


def _install_dispatcharr(
    monkeypatch,
    client,
):
    stub = types.ModuleType(
        "dispatcharr_admin"
    )

    class DispatcharrAdminClient:
        @classmethod
        def from_environment(cls):
            return client

    stub.DispatcharrAdminClient = (
        DispatcharrAdminClient
    )
    stub.DispatcharrAdminError = (
        FakeDispatcharrAdminError
    )

    monkeypatch.setitem(
        sys.modules,
        "dispatcharr_admin",
        stub,
    )


def _request(
    module,
    monkeypatch,
    *,
    store,
    client,
    payload,
):
    _install_dispatcharr(
        monkeypatch,
        client,
    )

    monkeypatch.setattr(
        module.Handler,
        "_source_store",
        staticmethod(
            lambda: store
        ),
    )

    monkeypatch.setenv(
        "ATLAS_SPORTS_WRITER_TOKEN",
        "test-token",
    )

    server = module.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        module.Handler,
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()

    try:
        host, port = (
            server.server_address
        )

        request = urllib.request.Request(
            (
                f"http://{host}:{port}"
                "/internal/v1/"
                "provider-accounts"
            ),
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Authorization": (
                    "Bearer test-token"
                ),
                "Content-Type": (
                    "application/json"
                ),
            },
            method="POST",
        )

        try:
            response = (
                urllib.request.urlopen(
                    request,
                    timeout=2,
                )
            )

            return (
                response.status,
                json.loads(
                    response.read()
                    .decode("utf-8")
                ),
            )

        except urllib.error.HTTPError as exc:
            return (
                exc.code,
                json.loads(
                    exc.read()
                    .decode("utf-8")
                ),
            )

    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _payload():
    return {
        "source_id": "xc4-account",
        "provider_id": "xc4",
        "provider_display_name": "XC4",
        "account_display_name": (
            "XC4 Main"
        ),
        "server_url": (
            "https://provider.example"
        ),
        "username": "xc4-user",
        "password": "xc4-secret",
        "max_connections": 4,
        "priority": 120,
    }


def test_private_create_is_compensated_and_secret_safe(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )
    store = FakeStore()
    client = FakeClient()

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
        payload=_payload(),
    )

    assert status == 201

    assert len(store.sources) == 1

    source = store.sources[0]

    assert source.source_id == (
        "xc4-account"
    )
    assert source.provider_id == "xc4"
    assert source.enabled is False
    assert source.max_connections == 4
    assert source.backend_reference == (
        "dispatcharr:m3u:42"
    )

    assert client.creates == [
        {
            "name": "xc4-account",
            "server_url": (
                "https://provider.example"
            ),
            "username": "xc4-user",
            "password": "xc4-secret",
            "max_connections": 4,
        }
    ]

    assert client.deletes == []

    rendered = json.dumps(
        body
    ).lower()

    for forbidden in (
        "xc4-secret",
        "xc4-user",
        "provider.example",
        "server_url",
        "username",
        "password",
    ):
        assert forbidden not in rendered


def test_private_create_compensates_state_write_failure(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )
    store = FakeStore(
        fail_write=True
    )
    client = FakeClient()

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
        payload=_payload(),
    )

    assert status == 503
    assert body == {
        "code": (
            "sports_provider_account_"
            "create_failed"
        ),
        "error": (
            "Provider account creation "
            "could not be persisted."
        ),
    }

    assert client.deletes == [42]


def test_private_create_reports_failed_compensation(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )
    store = FakeStore(
        fail_write=True
    )
    client = FakeClient(
        fail_delete=True
    )

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
        payload=_payload(),
    )

    assert status == 503
    assert body == {
        "code": (
            "sports_provider_account_"
            "reconciliation_required"
        ),
        "error": (
            "Provider account creation "
            "requires operator "
            "reconciliation."
        ),
    }


def test_private_create_rejects_duplicate_before_dispatcharr(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )

    existing = (
        module.SportsSource
        .from_mapping(
            {
                "source_id": (
                    "xc4-account"
                ),
                "display_name": (
                    "Existing"
                ),
                "provider_id": "xc4",
                "provider_display_name": (
                    "XC4"
                ),
                "account_display_name": (
                    "Existing"
                ),
                "kind": (
                    "licensed_subscription"
                ),
                "enabled": False,
                "priority": 100,
                "max_connections": 1,
                "backend_reference": (
                    "dispatcharr:m3u:7"
                ),
            }
        )
    )

    store = FakeStore(
        sources=(existing,)
    )
    client = FakeClient()

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
        payload=_payload(),
    )

    assert status == 409
    assert body["code"] == (
        "sports_source_exists"
    )
    assert client.creates == []
    assert store.writes == []


@pytest.mark.parametrize(
    "extra_field",
    (
        "backend_reference",
        "enabled",
        "account_type",
        "token",
        "api_key",
    ),
)
def test_private_create_rejects_unsupported_fields(
    monkeypatch,
    extra_field,
) -> None:
    module = _load_private_api(
        monkeypatch
    )
    store = FakeStore()
    client = FakeClient()

    payload = _payload()
    payload[extra_field] = "forbidden"

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
        payload=payload,
    )

    assert status == 422
    assert body["code"] == (
        "sports_provider_account_invalid"
    )
    assert client.creates == []
    assert store.writes == []


def test_private_create_rejects_conflicting_provider_group(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )

    existing = (
        module.SportsSource
        .from_mapping(
            {
                "source_id": (
                    "xc4-existing"
                ),
                "display_name": (
                    "Existing XC4"
                ),
                "provider_id": "xc4",
                "provider_display_name": (
                    "Existing Provider Name"
                ),
                "account_display_name": (
                    "Existing XC4"
                ),
                "kind": (
                    "licensed_subscription"
                ),
                "enabled": False,
                "priority": 100,
                "max_connections": 1,
                "backend_reference": (
                    "dispatcharr:m3u:7"
                ),
            }
        )
    )

    store = FakeStore(
        sources=(existing,)
    )
    client = FakeClient()

    payload = _payload()
    payload[
        "provider_display_name"
    ] = "Conflicting Provider Name"

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
        payload=payload,
    )

    assert status == 422
    assert body["code"] == (
        "sports_provider_account_invalid"
    )

    # Aggregate provider identity is validated
    # before Dispatcharr is touched.
    assert client.creates == []
    assert client.deletes == []
    assert store.writes == []
