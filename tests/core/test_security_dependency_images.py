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
