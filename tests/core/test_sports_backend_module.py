"""Static contracts for the private Sports backend module."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules" / "sports-backend"
COMPOSE = MODULE / "docker-compose.yml"
CONF = MODULE / "module.conf"
ENV_EXAMPLE = MODULE / ".env.example"
BACKUP_DOC = ROOT / "docs" / "architecture" / "BACKUP_RECOVERY.md"


def test_sports_backend_module_declares_expected_services() -> None:
    conf = CONF.read_text(encoding="utf-8")

    assert 'ATLAS_MODULE_NAME="sports-backend"' in conf
    assert 'ATLAS_MODULE_DEPENDENCIES="sports"' in conf
    assert (
        'ATLAS_MODULE_SERVICES="atlas-dispatcharr|atlas-teamarr"'
        in conf
    )


def test_sports_backend_has_no_public_port_or_ingress_contract() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "\n    ports:" not in compose
    assert "atlas-ingress" not in compose
    assert "atlas-backend" not in compose
    assert "no-new-privileges:true" in compose


def test_sports_backend_uses_persistent_storage_roots() -> None:
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "/mnt/storage/configs/dispatcharr" in example
    assert "/mnt/storage/configs/teamarr" in example
    assert "DISPATCHARR_DATA_DIR" in compose
    assert "TEAMARR_DATA_DIR" in compose


def test_sports_backend_does_not_define_end_user_identity() -> None:
    combined = (
        CONF.read_text(encoding="utf-8")
        + COMPOSE.read_text(encoding="utf-8")
        + ENV_EXAMPLE.read_text(encoding="utf-8")
    ).lower()

    assert "jellyfin_user_id" not in combined
    assert "atlas_user_id" not in combined


def test_sports_backend_state_is_documented_for_backup() -> None:
    text = BACKUP_DOC.read_text(encoding="utf-8")

    assert "/mnt/storage/configs/dispatcharr" in text
    assert "/mnt/storage/configs/teamarr" in text
    assert "Atlas-to-Jellyfin user linkage" in text


def test_dispatcharr_explicitly_uses_aio_mode() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert 'ghcr.io/dispatcharr/dispatcharr:latest' in compose
    assert 'DISPATCHARR_ENV: "aio"' in compose
    assert ':/data"' in compose


def test_teamarr_uses_stable_image_and_data_mount() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert 'ghcr.io/pharaoh-labs/teamarr:latest' in compose
    assert ':/app/data"' in compose
