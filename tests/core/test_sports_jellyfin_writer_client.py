from __future__ import annotations

import json
import importlib
import sys
import urllib.error
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPORTS_SRC = (
    ROOT
    / "modules"
    / "sports"
    / "src"
)


def _client_module():
    path = str(SPORTS_SRC)

    if path not in sys.path:
        sys.path.insert(
            0,
            path,
        )

    sys.modules.pop(
        "jellyfin_writer_client",
        None,
    )

    return importlib.import_module(
        "jellyfin_writer_client"
    )


class _Response:
    def __init__(
        self,
        body: bytes,
    ) -> None:
        self._body = body

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> bool:
        return False

    def read(
        self,
    ) -> bytes:
        return self._body


def test_refresh_uses_fixed_semantic_route_and_bearer_token(
) -> None:
    module = _client_module()

    seen: dict[str, object] = {}

    def opener(
        request,
        *,
        timeout,
    ):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["authorization"] = (
            request.get_header(
                "Authorization"
            )
        )
        seen["timeout"] = timeout
        seen["data"] = request.data

        return _Response(
            b'{"status":"completed",'
            b'"task_key":"RefreshGuide"}'
        )

    client = module.JellyfinWriterClient(
        base_url=(
            "http://atlas-jellyfin-writer:8004"
        ),
        token="writer-secret",
        timeout_seconds=75,
        opener=opener,
    )

    client.refresh_live_tv()

    assert seen == {
        "url": (
            "http://atlas-jellyfin-writer:8004"
            "/internal/v1/jellyfin/live-tv/refresh"
        ),
        "method": "POST",
        "authorization": (
            "Bearer writer-secret"
        ),
        "timeout": 75.0,
        "data": None,
    }


def test_environment_defaults_to_cross_compose_writer_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _client_module()

    monkeypatch.delenv(
        "ATLAS_JELLYFIN_WRITER_URL",
        raising=False,
    )
    monkeypatch.delenv(
        "ATLAS_JELLYFIN_WRITER_TIMEOUT_SECONDS",
        raising=False,
    )
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_WRITER_TOKEN",
        "writer-secret",
    )

    client = (
        module.JellyfinWriterClient
        .from_environment()
    )

    assert client._base_url == (
        "http://atlas-jellyfin-writer:8004"
    )
    assert client._timeout_seconds == 75.0


@pytest.mark.parametrize(
    "token",
    (
        "",
        "   ",
        "CHANGE_ME",
    ),
)
def test_writer_token_is_required(
    token: str,
) -> None:
    module = _client_module()

    with pytest.raises(
        ValueError,
        match="token is required",
    ):
        module.JellyfinWriterClient(
            base_url=(
                "http://atlas-jellyfin-writer:8004"
            ),
            token=token,
        )


def test_invalid_refresh_result_fails_closed(
) -> None:
    module = _client_module()

    client = module.JellyfinWriterClient(
        base_url=(
            "http://atlas-jellyfin-writer:8004"
        ),
        token="writer-secret",
        opener=lambda request, *, timeout: _Response(
            b'{"status":"completed",'
            b'"task_key":"OtherTask"}'
        ),
    )

    with pytest.raises(
        module.JellyfinWriterClientError,
        match="invalid refresh result",
    ):
        client.refresh_live_tv()


def test_upstream_error_body_is_never_exposed(
) -> None:
    module = _client_module()

    secret_body = (
        "upstream-secret-detail"
    )

    def opener(
        request,
        *,
        timeout,
    ):
        raise urllib.error.HTTPError(
            request.full_url,
            502,
            secret_body,
            None,
            None,
        )

    client = module.JellyfinWriterClient(
        base_url=(
            "http://atlas-jellyfin-writer:8004"
        ),
        token="writer-secret",
        opener=opener,
    )

    with pytest.raises(
        module.JellyfinWriterClientError,
    ) as captured:
        client.refresh_live_tv()

    assert secret_body not in str(
        captured.value
    )


def test_runtime_contract_uses_root_owned_token_and_module_url(
) -> None:
    compose = (
        ROOT
        / "modules"
        / "sports"
        / "docker-compose.yml"
    ).read_text(
        encoding="utf-8"
    )

    module_env = (
        ROOT
        / "modules"
        / "sports"
        / ".env.example"
    ).read_text(
        encoding="utf-8"
    )

    root_env = (
        ROOT
        / ".env.example"
    ).read_text(
        encoding="utf-8"
    )

    controller = compose.split(
        "  atlas-sports-controller:\n",
        1,
    )[1].split(
        "\nnetworks:",
        1,
    )[0]

    assert (
        'ATLAS_JELLYFIN_WRITER_URL: '
        '"${ATLAS_JELLYFIN_WRITER_URL:-'
        'http://atlas-jellyfin-writer:8004}"'
        in controller
    )

    assert (
        'ATLAS_JELLYFIN_WRITER_TOKEN: '
        '"${ATLAS_JELLYFIN_WRITER_TOKEN:'
        '?ATLAS_JELLYFIN_WRITER_TOKEN is required}"'
        in controller
    )

    assert (
        'ATLAS_JELLYFIN_WRITER_TIMEOUT_SECONDS: '
        '"${ATLAS_JELLYFIN_WRITER_TIMEOUT_SECONDS:-75}"'
        in controller
    )

    assert (
        "ATLAS_JELLYFIN_WRITER_URL="
        "http://atlas-jellyfin-writer:8004"
        in module_env
    )

    assert (
        "ATLAS_JELLYFIN_WRITER_TIMEOUT_SECONDS=75"
        in module_env
    )

    assert (
        "ATLAS_JELLYFIN_WRITER_TOKEN="
        not in module_env
    )

    assert (
        "ATLAS_JELLYFIN_WRITER_TOKEN=CHANGE_ME"
        in root_env
    )

    for forbidden in (
        "ATLAS_JELLYFIN_API_KEY",
        "ATLAS_JELLYFIN_URL",
        "JellyfinAdminClient",
    ):
        assert forbidden not in controller


def test_module_contract_requires_writer_client(
) -> None:
    module_conf = (
        ROOT
        / "modules"
        / "sports"
        / "module.conf"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "src/jellyfin_writer_client.py"
        in module_conf
    )


def _worker():
    path = str(SPORTS_SRC)

    if path not in sys.path:
        sys.path.insert(
            0,
            path,
        )

    sys.modules.pop(
        "worker",
        None,
    )

    return importlib.import_module(
        "worker"
    )


def _provider_result() -> dict[str, object]:
    current = {
        "id": "current-game",
        "provider": "thesportsdb",
        "provider_event_id": "event-1",
        "name": "Atlas One vs Atlas Two",
        "lifecycle_state": "live",
        "status": "live",
        "start_at": "2026-09-11T00:00:00Z",
    }

    return {
        "previous_games": {},
        "subscribed_previous_games": {},
        "provider_games": [current],
        "provider_health": {},
        "subscribed_games": [current],
        "degraded_count": 0,
    }


def test_operations_refresh_after_feed_before_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()
    provider_result = _provider_result()

    order: list[str] = []

    monkeypatch.setattr(
        worker,
        "prune_unmanaged_games",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        worker,
        "process_games",
        lambda games, *, publish_feed: {
            "current-game": games[0],
        },
    )

    monkeypatch.setattr(
        worker,
        "run_live_source_provisioning_pipeline",
        lambda games: (
            order.append("provision")
            or 1
        ),
    )

    monkeypatch.setattr(
        worker,
        "generate_feed_snapshot",
        lambda: (
            order.append("feed")
            or (
                0,
                ("sports-live-current",),
            )
        ),
    )

    monkeypatch.setattr(
        worker,
        "refresh_jellyfin_live_tv",
        lambda: order.append(
            "refresh"
        ),
    )

    monkeypatch.setattr(
        worker,
        "converge_jellyfin_live_tv_bindings",
        lambda channel_ids: (
            order.append("bind")
        ),
    )

    monkeypatch.setattr(
        worker,
        "write_provider_health",
        lambda health: order.append(
            "provider-health"
        ),
    )

    monkeypatch.setattr(
        worker,
        "write_heartbeat",
        lambda: order.append(
            "heartbeat"
        ),
    )

    monkeypatch.setattr(
        worker,
        "write_health_report",
        lambda: (
            order.append("health-report")
            or {"status": "healthy"}
        ),
    )

    monkeypatch.setattr(
        worker,
        "recording_counts",
        lambda recordings: {
            "pending": 0,
            "active": 0,
            "completed": 0,
        },
    )

    assert worker.run_operations_pipeline(
        provider_result,
        {},
    ) == 0

    assert order == [
        "provision",
        "feed",
        "refresh",
        "bind",
        "provider-health",
        "heartbeat",
        "health-report",
    ]


def test_writer_failure_prevents_health_and_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _worker()
    provider_result = _provider_result()

    later_calls: list[str] = []

    monkeypatch.setattr(
        worker,
        "prune_unmanaged_games",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        worker,
        "process_games",
        lambda games, *, publish_feed: {
            "current-game": games[0],
        },
    )

    monkeypatch.setattr(
        worker,
        "run_live_source_provisioning_pipeline",
        lambda games: 1,
    )

    monkeypatch.setattr(
        worker,
        "generate_feed_snapshot",
        lambda: (
            0,
            ("sports-live-current",),
        ),
    )

    def fail_refresh() -> None:
        raise RuntimeError(
            "synthetic Jellyfin writer failure"
        )

    monkeypatch.setattr(
        worker,
        "refresh_jellyfin_live_tv",
        fail_refresh,
    )

    monkeypatch.setattr(
        worker,
        "write_provider_health",
        lambda health: later_calls.append(
            "provider-health"
        ),
    )

    monkeypatch.setattr(
        worker,
        "write_heartbeat",
        lambda: later_calls.append(
            "heartbeat"
        ),
    )

    monkeypatch.setattr(
        worker,
        "write_health_report",
        lambda: (
            later_calls.append(
                "health-report"
            )
            or {"status": "healthy"}
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic Jellyfin writer failure",
    ):
        worker.run_operations_pipeline(
            provider_result,
            {},
        )

    assert later_calls == []


def test_inventory_get_returns_only_safe_channel_identity() -> None:
    import jellyfin_writer_client as module

    seen: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "channels": [
                        {
                            "item_id": "jellyfin-one",
                            "channel_number": "912345678",
                        },
                        {
                            "item_id": "jellyfin-two",
                            "channel_number": None,
                        },
                    ]
                }
            ).encode()

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["authorization"] = request.get_header(
            "Authorization"
        )
        seen["timeout"] = timeout
        return Response()

    client = module.JellyfinWriterClient(
        base_url="http://writer:8004",
        token="writer-token",
        timeout_seconds=19,
        opener=opener,
    )

    channels = client.list_live_tv_channels()

    assert channels == (
        module.JellyfinLiveTvChannel(
            item_id="jellyfin-one",
            channel_number="912345678",
        ),
        module.JellyfinLiveTvChannel(
            item_id="jellyfin-two",
            channel_number=None,
        ),
    )

    assert seen == {
        "url": (
            "http://writer:8004"
            "/internal/v1/jellyfin/live-tv/channels"
        ),
        "method": "GET",
        "authorization": "Bearer writer-token",
        "timeout": 19.0,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"channels": {}},
        {"channels": [{"item_id": "one"}]},
        {
            "channels": [
                {
                    "item_id": "",
                    "channel_number": "900000001",
                }
            ]
        },
        {
            "channels": [
                {
                    "item_id": "one",
                    "channel_number": 900000001,
                }
            ]
        },
        {
            "channels": [
                {
                    "item_id": "one",
                    "channel_number": "",
                }
            ]
        },
        {
            "channels": [
                {
                    "item_id": "one",
                    "channel_number": "900000001",
                    "name": "must-not-be-accepted",
                }
            ]
        },
    ],
)
def test_inventory_rejects_invalid_response_shape(
    payload,
) -> None:
    import jellyfin_writer_client as module

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                payload
            ).encode()

    client = module.JellyfinWriterClient(
        base_url="http://writer:8004",
        token="writer-token",
        opener=lambda *_args, **_kwargs: Response(),
    )

    with pytest.raises(
        module.JellyfinWriterClientError,
        match="invalid Live TV inventory",
    ):
        client.list_live_tv_channels()


def test_inventory_rejects_duplicate_jellyfin_item_ids() -> None:
    import jellyfin_writer_client as module

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "channels": [
                        {
                            "item_id": "ABC",
                            "channel_number": "900000001",
                        },
                        {
                            "item_id": "abc",
                            "channel_number": "900000002",
                        },
                    ]
                }
            ).encode()

    client = module.JellyfinWriterClient(
        base_url="http://writer:8004",
        token="writer-token",
        opener=lambda *_args, **_kwargs: Response(),
    )

    with pytest.raises(
        module.JellyfinWriterClientError,
        match="duplicate Live TV item identity",
    ):
        client.list_live_tv_channels()


def test_inventory_http_failure_is_sanitized() -> None:
    import urllib.error
    import jellyfin_writer_client as module

    secret = "upstream-secret-detail"

    def opener(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "http://writer:8004/"
            + secret,
            502,
            secret,
            {},
            None,
        )

    client = module.JellyfinWriterClient(
        base_url="http://writer:8004",
        token="writer-token",
        opener=opener,
    )

    with pytest.raises(
        module.JellyfinWriterClientError
    ) as captured:
        client.list_live_tv_channels()

    message = str(
        captured.value
    )

    assert secret not in message
    assert (
        message
        == "Jellyfin writer request failed."
    )
