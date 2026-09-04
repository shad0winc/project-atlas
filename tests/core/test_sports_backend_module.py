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
    assert 'ATLAS_MODULE_DEPENDS_MODULES="sports"' in conf
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

    assert (
        "ghcr.io/dispatcharr/dispatcharr@"
        "sha256:e764cd3fb3a4b14e0c96eeb830cce645"
        "b44ef0a2494838e21462c71dde5abeb4"
    ) in compose
    assert 'DISPATCHARR_ENV: "aio"' in compose
    assert ':/data"' in compose


def test_teamarr_uses_stable_image_and_data_mount() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert (
        "ghcr.io/pharaoh-labs/teamarr@"
        "sha256:d846ec078cde27f68e94f5fc3eec7f1"
        "ec29eca11f653b157ac352fef84b73c0c"
    ) in compose
    assert ':/app/data"' in compose


def test_sports_backend_images_are_immutable_digest_pins() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert (
        "ghcr.io/dispatcharr/dispatcharr@"
        "sha256:e764cd3fb3a4b14e0c96eeb830cce645"
        "b44ef0a2494838e21462c71dde5abeb4"
    ) in compose

    assert (
        "ghcr.io/pharaoh-labs/teamarr@"
        "sha256:d846ec078cde27f68e94f5fc3eec7f1"
        "ec29eca11f653b157ac352fef84b73c0c"
    ) in compose

    assert ":latest" not in compose


def test_sports_backend_runtime_scripts_are_declared() -> None:
    conf = CONF.read_text(encoding="utf-8")

    for name in (
        "scripts/install.sh",
        "scripts/uninstall.sh",
        "scripts/update.sh",
        "scripts/verify.sh",
        "scripts/health.py",
    ):
        assert name in conf


def test_sports_backend_install_preserves_private_boundary() -> None:
    install = (
        MODULE / "scripts" / "install.sh"
    ).read_text(encoding="utf-8")

    uninstall = (
        MODULE / "scripts" / "uninstall.sh"
    ).read_text(encoding="utf-8")

    assert "/mnt/storage/configs/dispatcharr" in install
    assert "/mnt/storage/configs/teamarr" in install
    assert "docker compose" in install

    assert "docker compose" in uninstall
    assert "Persistent state was preserved" in uninstall

    assert "rm -rf" not in uninstall
    assert "docker volume rm" not in uninstall
