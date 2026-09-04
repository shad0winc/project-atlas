from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _service_block(compose: str, service: str, next_service: str) -> str:
    start = compose.index(f"\n  {service}:\n")
    end = compose.index(f"\n  {next_service}:\n", start)
    return compose[start:end]


def test_public_api_does_not_initialize_live_session_policy() -> None:
    source = (ROOT / "apps/api/atlas_api/dependencies.py").read_text(encoding="utf-8")
    start = source.index("def get_live_session_policy_store()")
    end = source.index("\n\n@lru_cache", start)
    block = source[start:end]
    assert "default_live_session_policy_store()" in block
    assert ".initialize()" not in block


def test_public_api_users_mount_remains_read_only() -> None:
    compose = (ROOT / "stack/ingress.yml").read_text(encoding="utf-8")
    api = _service_block(compose, "api", "identity-writer")
    users_mount = (
        "/mnt/storage/configs/atlas/users:"
        "/mnt/storage/configs/atlas/users"
    )
    assert f"{users_mount}:ro" in api


def test_identity_writer_retains_writable_users_mount() -> None:
    import re

    compose = (ROOT / "stack/ingress.yml").read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^  identity-writer:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\\Z)",
        compose,
    )
    assert match is not None
    writer = match.group(0)
    users_mount = (
        "/mnt/storage/configs/atlas/users:"
        "/mnt/storage/configs/atlas/users"
    )
    assert f"{users_mount}:rw" in writer
