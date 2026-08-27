"""Security contracts for the privileged identity-mutation runtime."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGRESS_COMPOSE = PROJECT_ROOT / "stack" / "ingress.yml"


def _service_block(
    content: str,
    service: str,
    next_service: str,
) -> str:
    start = content.index(f"\n  {service}:\n")
    end = content.index(
        f"\n  {next_service}:\n",
        start + 1,
    )
    return content[start:end]


def test_identity_writer_is_private_and_least_privileged() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")
    writer = _service_block(
        content,
        "identity-writer",
        "caddy",
    )

    assert "      - atlas-identity\n" in writer
    assert "      - atlas-ingress\n" not in writer
    assert "      - atlas-backend\n" not in writer

    assert "    ports:\n" not in writer

    assert "    security_opt:\n" in writer
    assert "      - no-new-privileges:true\n" in writer

    assert "    read_only: true\n" in writer

    assert (
        "      - /mnt/storage/configs/atlas/users:"
        "/mnt/storage/configs/atlas/users:rw\n"
    ) in writer

    assert (
        "      - /mnt/storage/configs/atlas/identity/invitations:"
        "/mnt/storage/configs/atlas/identity/invitations:rw\n"
    ) in writer

    assert (
        "      - /mnt/storage/configs/atlas/identity:"
        "/mnt/storage/configs/atlas/identity:rw\n"
    ) not in writer

    assert (
        "/mnt/storage/configs/atlas/identity/favorites:"
    ) not in writer

    assert (
        "/mnt/storage/configs/atlas/runtime/requests:"
    ) not in writer

    assert (
        "/mnt/storage/configs/atlas/runtime/events.jsonl:"
    ) not in writer


def test_identity_writer_uses_canonical_identity_paths() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")
    writer = _service_block(
        content,
        "identity-writer",
        "caddy",
    )

    assert (
        '      ATLAS_USERS_DIR: '
        '"/mnt/storage/configs/atlas/users"\n'
    ) in writer

    assert (
        '      ATLAS_IDENTITY_DIR: '
        '"/mnt/storage/configs/atlas/identity"\n'
    ) in writer

    assert (
        "/mnt/storage/configs/atlas/users/invitations"
    ) not in writer


def test_identity_writer_requires_dedicated_service_authentication() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")
    writer = _service_block(
        content,
        "identity-writer",
        "caddy",
    )

    assert (
        '      ATLAS_IDENTITY_WRITER_TOKEN: '
        '"${ATLAS_IDENTITY_WRITER_TOKEN:'
        '?ATLAS_IDENTITY_WRITER_TOKEN is required}"\n'
    ) in writer

    assert "${ATLAS_IDENTITY_WRITER_TOKEN:-" not in writer

    # The privileged writer must not inherit the browser/session signing secret.
    assert "ATLAS_JWT_SECRET" not in writer


def test_public_api_retains_read_only_user_identity_state() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")
    api = _service_block(
        content,
        "api",
        "identity-writer",
    )

    assert (
        "      - /mnt/storage/configs/atlas/users:"
        "/mnt/storage/configs/atlas/users:ro\n"
    ) in api

    assert (
        "/mnt/storage/configs/atlas/users:"
        "/mnt/storage/configs/atlas/users:rw"
    ) not in api


def test_public_ingress_services_cannot_reach_identity_writer() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")

    portal = _service_block(
        content,
        "portal",
        "api",
    )

    caddy_start = content.index("\n  caddy:\n")
    networks_start = content.rindex("\nnetworks:\n")
    caddy = content[caddy_start:networks_start]

    assert "atlas-identity" not in portal
    assert "atlas-identity" not in caddy
