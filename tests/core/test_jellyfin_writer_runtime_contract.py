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


def test_jellyfin_writer_inventory_route_is_private_and_read_only(
) -> None:
    source = (
        ROOT
        / "apps"
        / "api"
        / "atlas_api"
        / "jellyfin_writer.py"
    ).read_text(
        encoding="utf-8"
    )

    route = (
        '@app.get(\n'
        '    "/internal/v1/jellyfin/live-tv/channels",'
    )

    assert route in source

    start = source.index(
        route
    )

    end = source.index(
        "\n\n@app.post(",
        start,
    )

    inventory = source[
        start:end
    ]

    assert (
        "dependencies=[Depends(_require_service_token)]"
        in inventory
    )

    assert (
        ".list_live_tv_channels()"
        in inventory
    )

    assert '"item_id"' in inventory
    assert '"channel_number"' in inventory

    for forbidden in (
        '"name"',
        '"type"',
        "ChannelId",
        "MediaSources",
        '"Path"',
        "start_scheduled_task",
        "find_scheduled_task_by_key",
    ):
        assert forbidden not in inventory


def test_jellyfin_writer_inventory_reuses_safe_provider_boundary(
) -> None:
    source = (
        ROOT
        / "apps"
        / "api"
        / "atlas_api"
        / "jellyfin_writer.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "from atlas.media.jellyfin import "
        "JellyfinProvider"
        in source
    )

    assert (
        "from atlas.media.provider import "
        "MediaProviderError"
        in source
    )

    assert (
        "def _jellyfin_provider() "
        "-> JellyfinProvider:"
        in source
    )


def test_jellyfin_writer_inventory_does_not_add_sports_credentials(
) -> None:
    sports = (
        ROOT
        / "modules"
        / "sports"
    )

    content = "\n".join(
        path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        for path in sports.rglob("*")
        if path.is_file()
    )

    assert "ATLAS_JELLYFIN_API_KEY" not in content
    assert "JellyfinProvider" not in content
