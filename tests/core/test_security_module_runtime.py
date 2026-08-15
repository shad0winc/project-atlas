"""Least-privilege contracts for first-party Atlas module runtimes."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

NOTIFICATIONS_COMPOSE = (
    PROJECT_ROOT / "modules" / "notifications" / "docker-compose.yml"
)
SPORTS_COMPOSE = PROJECT_ROOT / "modules" / "sports" / "docker-compose.yml"

NOTIFICATIONS_UPDATE = (
    PROJECT_ROOT / "modules" / "notifications" / "scripts" / "update.sh"
)
SPORTS_UPDATE = (
    PROJECT_ROOT / "modules" / "sports" / "scripts" / "update.sh"
)


def test_module_compose_requires_operator_identity() -> None:
    for path in (NOTIFICATIONS_COMPOSE, SPORTS_COMPOSE):
        content = path.read_text(encoding="utf-8")

        assert 'PUID: "${PUID:?PUID is required}"' in content
        assert 'PGID: "${PGID:?PGID is required}"' in content
        assert "${PUID:-1000}" not in content
        assert "${PGID:-1000}" not in content


def test_module_workers_prevent_privilege_escalation() -> None:
    for path in (NOTIFICATIONS_COMPOSE, SPORTS_COMPOSE):
        content = path.read_text(encoding="utf-8")

        assert "security_opt:" in content
        assert "no-new-privileges:true" in content


def test_notifications_runtime_bus_mounts_are_narrow() -> None:
    content = NOTIFICATIONS_COMPOSE.read_text(encoding="utf-8")

    broad_mount = (
        "/mnt/storage/configs/atlas/runtime:"
        "/mnt/storage/configs/atlas/runtime"
    )

    assert broad_mount not in content

    assert (
        "/mnt/storage/configs/atlas/runtime/events.jsonl:"
        "/mnt/storage/configs/atlas/runtime/events.jsonl:ro"
    ) in content

    assert (
        "/mnt/storage/configs/atlas/runtime/subscribers/"
        "module-notifications.cursor:"
        "/mnt/storage/configs/atlas/runtime/subscribers/"
        "module-notifications.cursor"
    ) in content

    assert (
        "/mnt/storage/configs/atlas/runtime/subscribers/"
        "module-notifications.filter:"
        "/mnt/storage/configs/atlas/runtime/subscribers/"
        "module-notifications.filter:ro"
    ) in content


def test_sports_controller_has_no_atlas_runtime_mount() -> None:
    content = SPORTS_COMPOSE.read_text(encoding="utf-8")

    assert "/mnt/storage/configs/atlas/runtime:" not in content


def test_sports_controller_has_no_private_scheduler_state_contract() -> None:
    content = SPORTS_COMPOSE.read_text(encoding="utf-8")

    assert "SPORTS_TASK_SCHEDULER_STATE_FILE" not in content
    assert "runtime/scheduler/sports.json" not in content


def test_module_updates_use_explicit_operator_environment() -> None:
    for path in (NOTIFICATIONS_UPDATE, SPORTS_UPDATE):
        content = path.read_text(encoding="utf-8")

        assert '--env-file "$OPERATOR_ENV_FILE"' in content
        assert "Numeric PUID and PGID are required" in content


def test_sports_update_fails_closed_on_ownership_mismatch() -> None:
    content = SPORTS_UPDATE.read_text(encoding="utf-8")

    assert "Sports runtime ownership precondition failed" in content
    assert "Refusing to recreate the non-root Sports controller." in content


def test_notifications_update_protects_runtime_bus_transition() -> None:
    content = NOTIFICATIONS_UPDATE.read_text(encoding="utf-8")

    assert "Notifications cursor ownership precondition failed" in content
    assert "cannot read the Runtime Bus event journal" in content
    assert "cannot read its Runtime Bus filter" in content
    assert "Refusing to recreate the non-root Notifications worker." in content


def test_sports_install_establishes_non_root_runtime_ownership() -> None:
    install = PROJECT_ROOT / "modules" / "sports" / "scripts" / "install.sh"
    content = install.read_text(encoding="utf-8")

    assert 'OPERATOR_ENV_FILE="$PROJECT_DIR/.env"' in content
    assert "Numeric PUID and PGID are required" in content
    assert "required_writable_paths=(" in content
    assert 'chown "$puid:$pgid" "${required_writable_paths[@]}"' in content
    assert "Sports runtime ownership installation failed" in content


def test_sports_update_has_explicit_compose_project_boundary() -> None:
    content = SPORTS_UPDATE.read_text(encoding="utf-8")

    assert content.count("--project-name sports") == 3


def test_sports_update_does_not_remove_cross_project_orphans() -> None:
    content = SPORTS_UPDATE.read_text(encoding="utf-8")

    assert "--remove-orphans" not in content


def test_sports_runtime_event_publisher_uses_repo_atlas_cli() -> None:
    content = SPORTS_COMPOSE.read_text(encoding="utf-8")

    assert (
        '      ATLAS_BINARY: "/opt/project-atlas/scripts/atlas"\n'
        in content
    )


def test_sports_feed_mounts_state_directory_read_only() -> None:
    content = SPORTS_COMPOSE.read_text(encoding="utf-8")

    assert (
        "      - /mnt/storage/configs/sportyfin/state:"
        "/etc/nginx/sports-state:ro\n"
        in content
    )
    assert (
        "/mnt/storage/configs/sportyfin/state/health.json:"
        "/etc/nginx/sports-health.json:ro"
        not in content
    )


def test_sports_health_alias_uses_directory_backed_state_mount() -> None:
    nginx = (
        PROJECT_ROOT
        / "modules"
        / "sports"
        / "config"
        / "nginx.conf"
    ).read_text(encoding="utf-8")

    assert "alias /etc/nginx/sports-state/health.json;" in nginx
    assert "alias /etc/nginx/sports-health.json;" not in nginx
