from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_notifications_verify_uses_nonruntime_source_for_compose_validation() -> None:
    compose = read("modules/notifications/docker-compose.yml")
    verify = read("modules/notifications/scripts/verify.sh")

    assert (
        "${ATLAS_NOTIFICATIONS_SOURCE_DIR:"
        "?ATLAS_NOTIFICATIONS_SOURCE_DIR is required}"
        ":/opt/project-atlas:ro"
        in compose
    )
    assert (
        "ATLAS_NOTIFICATIONS_SOURCE_DIR="
        "/__atlas_notifications_verify_source__"
        in verify
    )

    # The validation sentinel must never become a Compose/default runtime source.
    assert "/__atlas_notifications_verify_source__" not in compose


def test_sports_compose_uses_configured_host_media_root() -> None:
    compose = read("modules/sports/docker-compose.yml")

    assert (
        '${ATLAS_MEDIA_ROOT:?ATLAS_MEDIA_ROOT is required}'
        '/Sports:/mnt/storage/media/Sports'
        in compose
    )
    assert (
        "      - /mnt/storage/media/Sports:/mnt/storage/media/Sports"
        not in compose
    )


def test_sports_update_checks_configured_host_media_root() -> None:
    update = read("modules/sports/scripts/update.sh")

    assert 'ATLAS_CONFIG_FILE="$PROJECT_DIR/config/atlas.conf"' in update
    assert 'source "$ATLAS_CONFIG_FILE"' in update
    assert "export ATLAS_MEDIA_ROOT" in update
    assert '"$ATLAS_MEDIA_ROOT/Sports"' in update


def test_sports_verify_exports_media_root_for_compose_interpolation() -> None:
    verify = read("modules/sports/scripts/verify.sh")

    assert 'source "$ATLAS_CONFIG_FILE"' in verify
    assert "export ATLAS_MEDIA_ROOT" in verify


def test_sports_container_internal_media_contract_stays_stable() -> None:
    recorder = read("modules/sports/src/recorder.py")
    maintenance = read("modules/sports/src/maintenance.py")

    assert '"/mnt/storage/media/Sports"' in recorder
    assert '"/mnt/storage/media/Sports"' in maintenance
