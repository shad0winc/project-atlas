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
