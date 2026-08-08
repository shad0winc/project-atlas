"""Regression tests for the production VPN fail-closed topology."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"


def _service_block(identifier: str) -> str:
    """Return one top-level Compose service block without parsing YAML."""

    lines = COMPOSE_FILE.read_text(encoding="utf-8").splitlines()
    header = f"  {identifier}:"

    try:
        start = lines.index(header)
    except ValueError as exc:
        raise AssertionError(
            f"Compose service is missing: {identifier}"
        ) from exc

    end = len(lines)

    for index in range(start + 1, len(lines)):
        line = lines[index]

        if (
            line.startswith("  ")
            and not line.startswith("    ")
            and line.endswith(":")
        ):
            end = index
            break

    return "\n".join(lines[start:end])


def test_qbittorrent_shares_only_gluetun_network_namespace() -> None:
    """qBittorrent must not receive an independent network path."""

    block = _service_block("qbittorrent")

    assert 'network_mode: "service:gluetun"' in block
    assert "\n    networks:" not in block
    assert "\n    ports:" not in block


def test_gluetun_owns_vpn_firewall_and_tunnel_boundary() -> None:
    """Gluetun must own the firewall capability and tunnel device."""

    block = _service_block("gluetun")

    assert "\n    cap_add:\n      - NET_ADMIN" in block
    assert "\n    devices:\n      - /dev/net/tun:/dev/net/tun" in block
    assert "\n      - FIREWALL=on" in block


def test_qbittorrent_ports_are_published_by_gluetun() -> None:
    """Shared-namespace qBittorrent ports must belong to Gluetun."""

    gluetun = _service_block("gluetun")
    qbittorrent = _service_block("qbittorrent")

    assert '${QBITTORRENT_PORT:-8080}:8080' in gluetun
    assert '"6881:6881"' in gluetun
    assert '"6881:6881/udp"' in gluetun
    assert "\n    ports:" not in qbittorrent


def test_qbittorrent_waits_for_gluetun_health() -> None:
    """Process startup alone must not satisfy VPN readiness."""

    gluetun = _service_block("gluetun")
    qbittorrent = _service_block("qbittorrent")

    assert "\n    healthcheck:" in gluetun
    assert "\n    depends_on:\n      gluetun:" in qbittorrent
    assert "\n        condition: service_healthy" in qbittorrent
