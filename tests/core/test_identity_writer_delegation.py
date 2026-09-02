"""Contracts for privileged identity mutation delegation."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ADMIN_USERS = (
    PROJECT_ROOT
    / "apps/api/atlas_api/routes/v1/admin_users.py"
)

ADMIN_INVITATIONS = (
    PROJECT_ROOT
    / "apps/api/atlas_api/routes/v1/admin_invitations.py"
)

DEPENDENCIES = (
    PROJECT_ROOT
    / "apps/api/atlas_api/dependencies.py"
)

INGRESS = PROJECT_ROOT / "stack/ingress.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def test_admin_user_mutation_delegates_to_writer() -> None:
    content = _text(ADMIN_USERS)

    assert "get_identity_writer_client" in content
    assert ".update_user(" in content

    # Public API must never regain durable user write authority.
    assert "profiles.update_user(" not in content


def test_admin_invitation_mutations_delegate_to_writer() -> None:
    content = _text(ADMIN_INVITATIONS)

    assert "get_identity_writer_client" in content
    assert ".create_invitation(" in content
    assert ".revoke_invitation(" in content

    assert "invitations.create(" not in content
    assert "invitations.revoke(" not in content


def test_admin_invitation_reads_use_canonical_identity_root() -> None:
    content = _text(ADMIN_INVITATIONS)

    assert "default_identity_paths" in content
    assert "IdentityPaths(profiles.root)" not in content


def test_api_has_identity_writer_dependency() -> None:
    content = _text(DEPENDENCIES)

    assert "def get_identity_writer_client(" in content
    assert "IdentityWriterClient" in content
    assert "ATLAS_IDENTITY_WRITER_URL" in content
    assert "ATLAS_IDENTITY_WRITER_TOKEN" in content


def test_api_runtime_receives_writer_connection_configuration() -> None:
    content = _text(INGRESS)
    api = _service_block(
        content,
        "api",
        "identity-writer",
    )

    assert (
        '      ATLAS_IDENTITY_WRITER_URL: '
        '"http://identity-writer:8001"\n'
    ) in api

    assert (
        '      ATLAS_IDENTITY_WRITER_TOKEN: '
        '"${ATLAS_IDENTITY_WRITER_TOKEN:'
        '?ATLAS_IDENTITY_WRITER_TOKEN is required}"\n'
    ) in api


def test_writer_runtime_has_healthcheck() -> None:
    content = _text(INGRESS)
    writer = _service_block(
        content,
        "identity-writer",
        "caddy",
    )

    assert "    healthcheck:\n" in writer
    assert "http://127.0.0.1:8001/health" in writer


def test_writer_client_is_narrowly_scoped() -> None:
    client = (
        PROJECT_ROOT
        / "apps/api/atlas_api/services/identity_writer.py"
    )

    assert client.is_file()

    content = _text(client)

    assert "class IdentityWriterClient" in content
    assert "def update_user(" in content
    assert "def create_invitation(" in content
    assert "def revoke_invitation(" in content

    # The client is mutation-only.
    assert "def list_users(" not in content
    assert "def get_user(" not in content
    assert "def list_invitations(" not in content
    assert "def get_invitation(" not in content
