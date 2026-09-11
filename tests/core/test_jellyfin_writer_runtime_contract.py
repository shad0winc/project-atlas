from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INGRESS = ROOT / "stack" / "ingress.yml"
UPDATE = ROOT / "scripts" / "commands" / "update.sh"
VERIFY = ROOT / "scripts" / "verify-ingress.sh"
ENV_EXAMPLE = ROOT / ".env.example"
WRITER = (
    ROOT
    / "apps"
    / "api"
    / "atlas_api"
    / "jellyfin_writer.py"
)


def _service_block(
    content: str,
    service: str,
    next_service: str,
) -> str:
    start = content.index(
        f"\n  {service}:\n"
    )
    end = content.index(
        f"\n  {next_service}:\n",
        start + 1,
    )
    return content[start:end]


def test_jellyfin_writer_is_private_and_least_privileged() -> None:
    content = INGRESS.read_text(
        encoding="utf-8"
    )
    writer = _service_block(
        content,
        "jellyfin-writer",
        "caddy",
    )

    assert (
        "container_name: atlas-jellyfin-writer"
        in writer
    )
    assert "      - atlas\n" in writer
    assert "atlas-identity" not in writer
    assert "atlas-ingress" not in writer
    assert "atlas-backend" not in writer
    assert "\n    ports:" not in writer
    assert '    expose:\n      - "8004"\n' in writer
    assert "    read_only: true\n" in writer
    assert "      - no-new-privileges:true\n" in writer
    assert "\n    volumes:" not in writer


def test_jellyfin_writer_owns_only_required_jellyfin_credentials() -> None:
    content = INGRESS.read_text(
        encoding="utf-8"
    )
    writer = _service_block(
        content,
        "jellyfin-writer",
        "caddy",
    )

    assert (
        'ATLAS_JELLYFIN_WRITER_TOKEN: '
        '"${ATLAS_JELLYFIN_WRITER_TOKEN:'
        '?ATLAS_JELLYFIN_WRITER_TOKEN is required}"'
        in writer
    )
    assert (
        'ATLAS_JELLYFIN_URL: "http://jellyfin:8096"'
        in writer
    )
    assert (
        'ATLAS_JELLYFIN_API_KEY: '
        '"${ATLAS_JELLYFIN_API_KEY:'
        '?ATLAS_JELLYFIN_API_KEY is required}"'
        in writer
    )
    assert "ATLAS_JWT_SECRET" not in writer
    assert "ATLAS_SPORTS_WRITER_TOKEN" not in writer
    assert "DISPATCHARR_" not in writer


def test_jellyfin_writer_does_not_expand_identity_network() -> None:
    content = INGRESS.read_text(
        encoding="utf-8"
    )
    assert (
        content.count(
            "      - atlas-identity\n"
        )
        == 4
    )


def test_jellyfin_writer_has_dedicated_secret_template() -> None:
    content = ENV_EXAMPLE.read_text(
        encoding="utf-8"
    )
    assert (
        "ATLAS_JELLYFIN_WRITER_TOKEN=CHANGE_ME"
        in content
    )


def test_jellyfin_writer_exposes_only_semantic_refresh_route() -> None:
    content = WRITER.read_text(
        encoding="utf-8"
    )

    assert (
        '"/internal/v1/jellyfin/live-tv/refresh"'
        in content
    )
    assert 'REFRESH_TASK_KEY = "RefreshGuide"' in content
    assert "find_scheduled_task_by_key(" in content
    assert "start_scheduled_task(" in content
    assert "task_key:" not in content
    assert "task_id:" not in content


def test_update_reuses_api_image_and_waits_for_writer() -> None:
    content = UPDATE.read_text(
        encoding="utf-8"
    )

    assert "\n    build portal api sports-writer" in content
    assert (
        "\n    build portal api sports-writer "
        "jellyfin-writer"
        not in content
    )
    assert "atlas-jellyfin-writer" in content


def test_ingress_verification_requires_jellyfin_writer() -> None:
    content = VERIFY.read_text(
        encoding="utf-8"
    )
    assert "atlas-jellyfin-writer" in content
