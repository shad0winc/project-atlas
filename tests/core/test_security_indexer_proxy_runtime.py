"""Security contracts for the isolated indexer-proxy boundary."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_COMPOSE = PROJECT_ROOT / "docker-compose.yml"


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


def test_indexer_proxy_bridge_is_declared() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    networks = content[
        content.index("\nnetworks:\n"):
        content.index("\nservices:\n")
    ]

    assert "  atlas-indexer-proxy:\n" in networks
    assert "    name: atlas-indexer-proxy\n" in networks
    assert "    driver: bridge\n" in networks


def test_prowlarr_bridges_atlas_and_indexer_proxy_networks() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    prowlarr = _service_block(
        content,
        "prowlarr",
        "flaresolverr",
    )

    assert "      - atlas\n" in prowlarr
    assert "      - atlas-indexer-proxy\n" in prowlarr


def test_flaresolverr_is_confined_to_indexer_proxy_bridge() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    flaresolverr = _service_block(
        content,
        "flaresolverr",
        "sonarr",
    )

    assert "      - atlas-indexer-proxy\n" in flaresolverr
    assert "      - atlas\n" not in flaresolverr
    assert "    ports:\n" not in flaresolverr
    assert "    volumes:\n" not in flaresolverr


def test_indexer_proxy_bridge_preserves_egress() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    start = content.index("  atlas-indexer-proxy:\n")
    end = content.index("\nservices:\n", start)
    network = content[start:end]

    assert "internal: true" not in network
