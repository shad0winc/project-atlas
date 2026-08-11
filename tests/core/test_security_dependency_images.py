"""Security contracts for remediated third-party dependency images."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_COMPOSE = PROJECT_ROOT / "docker-compose.yml"

MAINTAINERR_IMAGE = (
    "ghcr.io/maintainerr/maintainerr:3.21.1"
    "@sha256:"
    "811a580fdf479e8582d3c97047b1aa8930fc5523f63143498020864ad6a7cd80"
)

SEERR_IMAGE = (
    "ghcr.io/seerr-team/seerr:v3.4.1"
    "@sha256:"
    "f4768de5f616248d723e05891f3345a1402123775d03bf0890dbfedc0831bda1"
)


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


def test_maintainerr_uses_maintained_immutable_image() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    maintainerr = _service_block(
        content,
        "maintainerr",
        "tautulli",
    )

    assert f"    image: {MAINTAINERR_IMAGE}\n" in maintainerr
    assert "ghcr.io/jorenn92/maintainerr" not in content
    assert "maintainerr:latest" not in maintainerr


def test_maintainerr_preserves_non_root_runtime_identity() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    maintainerr = _service_block(
        content,
        "maintainerr",
        "tautulli",
    )

    assert '    user: "1000:1000"\n' in maintainerr


def test_maintainerr_preserves_existing_storage_contract() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    maintainerr = _service_block(
        content,
        "maintainerr",
        "tautulli",
    )

    assert "      - ${CONFIG}/maintainerr:/opt/data\n" in maintainerr
    assert "      - ${MEDIA}:/media\n" in maintainerr
    assert '"${MAINTAINERR_PORT:-6246}:6246"' in maintainerr


def test_jellyseerr_compatibility_service_uses_official_seerr_image() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    jellyseerr = _service_block(
        content,
        "jellyseerr",
        "bazarr",
    )

    assert f"    image: {SEERR_IMAGE}\n" in jellyseerr
    assert "fallenbagel/jellyseerr" not in content
    assert "    init: true\n" in jellyseerr


def test_seerr_preserves_atlas_jellyseerr_compatibility_identity() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    jellyseerr = _service_block(
        content,
        "jellyseerr",
        "bazarr",
    )

    assert "  jellyseerr:\n" in content
    assert "    container_name: jellyseerr\n" in jellyseerr
    assert '"${JELLYSEERR_PORT:-5055}:5055"' in jellyseerr


def test_seerr_preserves_existing_configuration_path() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    jellyseerr = _service_block(
        content,
        "jellyseerr",
        "bazarr",
    )

    assert "      - ${CONFIG}/jellyseerr:/app/config\n" in jellyseerr

def test_seerr_has_canonical_public_settings_healthcheck() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    jellyseerr = _service_block(
        content,
        "jellyseerr",
        "bazarr",
    )

    assert "    healthcheck:\n" in jellyseerr
    assert (
        "      test: wget --no-verbose --tries=1 --spider "
        "http://localhost:5055/api/v1/settings/public || exit 1\n"
        in jellyseerr
    )
    assert "      start_period: 20s\n" in jellyseerr
    assert "      timeout: 3s\n" in jellyseerr
    assert "      interval: 15s\n" in jellyseerr
    assert "      retries: 3\n" in jellyseerr
