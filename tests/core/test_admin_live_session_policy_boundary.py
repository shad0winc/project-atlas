from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _service_block(source: str, name: str) -> str:
    marker = f"\n  {name}:\n"
    start = source.index(marker) + 1
    tail = source[start:]
    lines = tail.splitlines(keepends=True)
    offset = 0
    end = len(tail)
    for index, line in enumerate(lines):
        if index > 0 and line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            end = offset
            break
        offset += len(line)
    return tail[:end]


def test_public_api_stays_read_only_for_live_policy() -> None:
    compose = (ROOT / "stack/ingress.yml").read_text(encoding="utf-8")
    api = _service_block(compose, "api")
    writer = _service_block(compose, "identity-writer")
    users_mount = "/mnt/storage/configs/atlas/users:/mnt/storage/configs/atlas/users"
    assert f"{users_mount}:ro" in api
    assert f"{users_mount}:rw" in writer


def test_public_admin_route_delegates_policy_mutations() -> None:
    route = (ROOT / "apps/api/atlas_api/routes/v1/admin_live_sessions.py").read_text(encoding="utf-8")
    assert "get_identity_writer_client" in route
    assert "set_live_session_default_limit" in route
    assert "set_live_session_user_override" in route
    assert "clear_live_session_user_override" in route
    assert ".initialize()" not in route


def test_private_writer_owns_durable_policy_mutations() -> None:
    private = (ROOT / "apps/api/atlas_api/identity_writer.py").read_text(encoding="utf-8")
    assert "/internal/v1/live-session-policy/default" in private
    assert "/internal/v1/live-session-policy/users/{user_id}" in private
    assert "default_live_session_policy_store" in private
    assert "Depends(_require_service_token)" in private
