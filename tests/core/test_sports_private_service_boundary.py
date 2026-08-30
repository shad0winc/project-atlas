"""Sports API private-service runtime boundary contracts."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGRESS = PROJECT_ROOT / "stack" / "ingress.yml"
SPORTS_SERVICE = (
    PROJECT_ROOT / "apps" / "api" / "atlas_api" / "services" / "sports.py"
)
PRIVATE_API = (
    PROJECT_ROOT / "modules" / "sports" / "src" / "private_api.py"
)
PRIVATE_DOCKERFILE = (
    PROJECT_ROOT / "modules" / "sports" / "Dockerfile.private-api"
)


def test_public_api_uses_private_sports_service() -> None:
    content = SPORTS_SERVICE.read_text(encoding="utf-8")
    assert "ATLAS_SPORTS_WRITER_URL" in content
    assert "ATLAS_SPORTS_WRITER_TOKEN" in content
    assert "/opt/project-atlas/modules/sports/src" not in content
    builder = content[content.index("def build_default_sports_api_service"):]
    assert "_load_sports_module_env" not in builder


def test_private_sports_service_is_not_published() -> None:
    content = INGRESS.read_text(encoding="utf-8")
    start = content.index("\n  sports-writer:\n")
    end = content.index("\n  identity-writer:\n", start)
    service = content[start:end]
    assert "container_name: atlas-sports-writer" in service
    assert "      - atlas-identity" in service
    assert '    expose:\n      - "8003"' in service
    assert "\n    ports:" not in service
    assert "/opt/project-atlas:/opt/project-atlas" not in service
    assert "env_file:" not in service
    assert "modules/sports/.env" not in service
    assert "Dockerfile.private-api" in service


def test_public_api_does_not_mount_sports_state() -> None:
    content = INGRESS.read_text(encoding="utf-8")
    start = content.index("\n  api:\n")
    end = content.index("\n  downloads-writer:\n", start)
    api = content[start:end]
    assert "/mnt/storage/configs/sportyfin" not in api
    assert "ATLAS_SPORTS_WRITER_URL" in api
    assert "ATLAS_SPORTS_WRITER_TOKEN" in api


def test_private_sports_service_requires_bearer_token() -> None:
    content = PRIVATE_API.read_text(encoding="utf-8")
    assert "hmac.compare_digest" in content
    assert "ATLAS_SPORTS_WRITER_TOKEN" in content
    assert 'supplied.startswith("Bearer ")' in content
    assert "MAX_BODY_BYTES" in content

def test_private_sports_image_packages_only_runtime_source() -> None:
    content = PRIVATE_DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY modules/sports/src/*.py /srv/sports/" not in content
    assert (
        "COPY modules/sports/src/private_api.py /srv/sports/private_api.py"
        in content
    )
    assert (
        "COPY modules/sports/src/subscriptions.py /srv/sports/subscriptions.py"
        in content
    )
    assert (
        "COPY modules/sports/src/providers /srv/sports/providers"
        in content
    )
    assert 'PYTHONDONTWRITEBYTECODE="1"' in content
    assert "COPY . " not in content
    assert "/opt/project-atlas" not in content
    assert "\nUSER atlas\n" in content


def _load_private_sports_api_for_failure_test(monkeypatch):
    import importlib.util
    import sys
    import types
    from pathlib import Path

    providers_package = types.ModuleType("providers")
    providers_package.__path__ = []
    registry_module = types.ModuleType("providers.registry")
    registry_module.enabled_providers = lambda: []

    subscriptions_module = types.ModuleType("subscriptions")
    subscriptions_module.load_subscriptions = lambda: []
    subscriptions_module.create_subscription = lambda *args, **kwargs: ({}, True)

    monkeypatch.setitem(sys.modules, "providers", providers_package)
    monkeypatch.setitem(sys.modules, "providers.registry", registry_module)
    monkeypatch.setitem(sys.modules, "subscriptions", subscriptions_module)

    source = (
        Path(__file__).resolve().parents[2]
        / "modules"
        / "sports"
        / "src"
        / "private_api.py"
    )
    spec = importlib.util.spec_from_file_location(
        "atlas_private_sports_failure_test",
        source,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_sports_provider_failure_returns_controlled_503(monkeypatch) -> None:
    import json
    import threading
    import urllib.error
    import urllib.request

    module = _load_private_sports_api_for_failure_test(monkeypatch)

    def failed_provider(name):
        raise RuntimeError("provider failure must not escape")

    monkeypatch.setattr(module, "_provider", failed_provider)
    monkeypatch.setenv("ATLAS_SPORTS_WRITER_TOKEN", "test-token")

    server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        request = urllib.request.Request(
            f"http://{host}:{port}/internal/v1/events"
            "?user_id=usr-test&provider=thesportsdb",
            headers={"Authorization": "Bearer test-token"},
            method="GET",
        )
        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as exc:
            assert exc.code == 503
            assert json.loads(exc.read().decode("utf-8")) == {
                "code": "sports_backend_unavailable",
                "error": "Sports provider or state service is unavailable.",
            }
        else:
            raise AssertionError("expected controlled private Sports 503")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_private_sports_subscription_storage_failure_returns_controlled_503(
    monkeypatch,
) -> None:
    import json
    import threading
    import urllib.error
    import urllib.request

    module = _load_private_sports_api_for_failure_test(monkeypatch)

    class Provider:
        name = "thesportsdb"

        def fetch_event(self, event_id):
            return {"id": event_id}

        def normalize_event(self, raw_event):
            return {
                "provider_event_id": "event-001",
                "name": "Test Event",
            }

    monkeypatch.setattr(module, "_provider", lambda name: Provider())

    def failed_store(*args, **kwargs):
        raise OSError("state failure must not escape")

    monkeypatch.setattr(module, "create_subscription", failed_store)
    monkeypatch.setenv("ATLAS_SPORTS_WRITER_TOKEN", "test-token")

    server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        body = json.dumps(
            {
                "user_id": "usr-test",
                "provider": "thesportsdb",
                "provider_event_id": "event-001",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"http://{host}:{port}/internal/v1/events/request",
            data=body,
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as exc:
            assert exc.code == 503
            assert json.loads(exc.read().decode("utf-8")) == {
                "code": "sports_backend_unavailable",
                "error": "Sports provider or state service is unavailable.",
            }
        else:
            raise AssertionError("expected controlled private Sports 503")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_private_sports_image_is_minimal_and_runtime_root_is_read_only() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    dockerfile = (
        root / "modules" / "sports" / "Dockerfile.private-api"
    ).read_text(encoding="utf-8")
    compose = (root / "stack" / "ingress.yml").read_text(encoding="utf-8")

    assert "COPY modules/sports/src/*.py" not in dockerfile
    assert (
        "COPY modules/sports/src/private_api.py /srv/sports/private_api.py"
        in dockerfile
    )
    assert (
        "COPY modules/sports/src/subscriptions.py /srv/sports/subscriptions.py"
        in dockerfile
    )
    assert "COPY modules/sports/src/providers /srv/sports/providers" in dockerfile
    assert 'PYTHONDONTWRITEBYTECODE="1"' in dockerfile

    start = compose.index("\n  sports-writer:\n")
    end = compose.index("\n  identity-writer:\n", start)
    sports_writer = compose[start:end]
    assert "    read_only: true\n" in sports_writer
    assert (
        "      - /mnt/storage/configs/sportyfin/state:"
        "/mnt/storage/configs/sportyfin/state:rw\n"
        in sports_writer
    )

