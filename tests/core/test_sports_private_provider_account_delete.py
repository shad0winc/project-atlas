from __future__ import annotations

import importlib.util
import json
import sys
import threading
import types
import urllib.error
import urllib.request
from pathlib import Path


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
        "account_delete"
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
                "simulated lifecycle failure"
            )

        self.sources = values


class FakeLiveSourceRegistry:
    def __init__(
        self,
        sources=(),
    ):
        self.sources = tuple(sources)

    def list_sources(self):
        return self.sources


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
        self.deletes = []
        self.fail_delete = fail_delete

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
                    "simulated backend failure"
                )
            )


def _source(
    module,
    *,
    enabled=False,
    backend_reference=(
        "dispatcharr:m3u:42"
    ),
):
    return (
        module.SportsSource
        .from_mapping(
            {
                "source_id": (
                    "xc4-account"
                ),
                "display_name": (
                    "XC4 Main"
                ),
                "provider_id": "xc4",
                "provider_display_name": (
                    "XC4"
                ),
                "account_display_name": (
                    "XC4 Main"
                ),
                "kind": (
                    "licensed_subscription"
                ),
                "enabled": enabled,
                "priority": 120,
                "max_connections": 4,
                "backend_reference": (
                    backend_reference
                ),
            }
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
    live_sources=(),
    source_id="xc4-account",
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

    monkeypatch.setattr(
        module,
        "default_live_source_registry",
        lambda: FakeLiveSourceRegistry(
            live_sources
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
                "provider-accounts/"
                f"{source_id}"
            ),
            headers={
                "Authorization": (
                    "Bearer test-token"
                ),
            },
            method="DELETE",
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


def test_private_delete_removes_backend_then_lifecycle(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )

    source = _source(module)
    store = FakeStore(
        sources=(source,)
    )
    client = FakeClient()

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
    )

    assert status == 200
    assert body == {
        "removed": True,
        "source_id": "xc4-account",
    }

    assert client.deletes == [42]
    assert store.sources == ()
    assert store.writes == [()]

    rendered = json.dumps(
        body
    ).lower()

    for forbidden in (
        "dispatcharr:m3u",
        "backend_reference",
        "username",
        "password",
        "server_url",
    ):
        assert forbidden not in rendered


def test_private_delete_requires_disabled_source(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )

    source = _source(
        module,
        enabled=True,
    )
    store = FakeStore(
        sources=(source,)
    )
    client = FakeClient()

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
    )

    assert status == 409
    assert body["code"] == (
        "sports_provider_account_enabled"
    )
    assert client.deletes == []
    assert store.writes == []


def test_private_delete_blocks_existing_live_sources(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )

    source = _source(module)
    store = FakeStore(
        sources=(source,)
    )
    client = FakeClient()

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
        live_sources=(
            object(),
        ),
    )

    assert status == 409
    assert body["code"] == (
        "sports_provider_account_"
        "playback_dependency"
    )
    assert client.deletes == []
    assert store.writes == []


def test_private_delete_backend_failure_keeps_lifecycle(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )

    source = _source(module)
    store = FakeStore(
        sources=(source,)
    )
    client = FakeClient(
        fail_delete=True
    )

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
    )

    assert status == 503
    assert body["code"] == (
        "dispatcharr_admin_unavailable"
    )

    assert client.deletes == [42]
    assert store.sources == (
        source,
    )
    assert store.writes == []


def test_private_delete_reports_post_backend_reconciliation(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )

    source = _source(module)
    store = FakeStore(
        sources=(source,),
        fail_write=True,
    )
    client = FakeClient()

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
    )

    assert status == 503
    assert body == {
        "code": (
            "sports_provider_account_"
            "reconciliation_required"
        ),
        "error": (
            "Provider account removal "
            "requires operator "
            "reconciliation."
        ),
    }

    assert client.deletes == [42]

    # Backend deletion already succeeded.
    # The disabled Atlas lifecycle record
    # remains available for reconciliation.
    assert store.sources == (
        source,
    )


def test_private_delete_rejects_invalid_backend_reference(
    monkeypatch,
) -> None:
    module = _load_private_api(
        monkeypatch
    )

    source = _source(
        module,
        backend_reference=(
            "invalid-reference"
        ),
    )
    store = FakeStore(
        sources=(source,)
    )
    client = FakeClient()

    status, body = _request(
        module,
        monkeypatch,
        store=store,
        client=client,
    )

    assert status == 422
    assert body["code"] == (
        "sports_provider_account_invalid"
    )
    assert client.deletes == []
    assert store.writes == []


def test_private_delete_missing_source_is_404(
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
    )

    assert status == 404
    assert body["code"] == (
        "sports_source_not_found"
    )
    assert client.deletes == []
    assert store.writes == []
