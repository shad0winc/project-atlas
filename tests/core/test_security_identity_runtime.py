"""Security contracts for the isolated API identity boundary."""

from __future__ import annotations

import stat
from pathlib import Path

from atlas.user_profiles import UserProfileStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_COMPOSE = PROJECT_ROOT / "docker-compose.yml"
INGRESS_COMPOSE = PROJECT_ROOT / "stack" / "ingress.yml"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _service_block(content: str, service: str, next_service: str) -> str:
    start = content.index(f"\n  {service}:\n")
    end = content.index(f"\n  {next_service}:\n", start + 1)
    return content[start:end]


def test_identity_state_creation_is_group_readable_not_world_readable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "users"
    store = UserProfileStore(root)
    profile = store.create_user("security-reader")

    profile_directory = (
        root / "profiles" / profile["user_id"]
    )
    profile_file = profile_directory / "profile.json"

    for directory in (
        root,
        root / "profiles",
        profile_directory,
    ):
        assert _mode(directory) & 0o777 == 0o750

    assert _mode(root / "users.json") == 0o640
    assert _mode(profile_file) == 0o640


def test_core_compose_limits_identity_network_to_jellyfin() -> None:
    content = CORE_COMPOSE.read_text(encoding="utf-8")
    jellyfin = _service_block(content, "jellyfin", "prowlarr")

    assert "  atlas-identity:\n" in content
    assert "    name: atlas-identity\n" in content
    assert "      - atlas\n" in jellyfin
    assert "      - atlas-identity\n" in jellyfin
    assert content.count("      - atlas-identity\n") == 1


def test_ingress_api_has_read_only_identity_access() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")
    api = _service_block(content, "api", "caddy")

    assert "      - atlas-ingress\n" in api
    assert "      - atlas-identity\n" in api
    assert '      - "20000"\n' in api
    assert (
        "      - /mnt/storage/configs/atlas/users:"
        "/mnt/storage/configs/atlas/users:ro\n"
    ) in api
    assert '      ATLAS_JELLYFIN_URL: "http://jellyfin:8096"\n' in api
    assert (
        '      ATLAS_USERS_DIR: "/mnt/storage/configs/atlas/users"\n'
    ) in api


def test_identity_network_is_not_shared_with_public_ingress_services() -> None:
    content = INGRESS_COMPOSE.read_text(encoding="utf-8")
    portal = _service_block(content, "portal", "api")
    caddy_start = content.index("\n  caddy:\n")
    networks_start = content.rindex("\nnetworks:\n")
    caddy = content[caddy_start:networks_start]

    assert "atlas-identity" not in portal
    assert "atlas-identity" not in caddy
    assert content.count("      - atlas-identity\n") == 1
