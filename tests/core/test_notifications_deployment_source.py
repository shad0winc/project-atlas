from __future__ import annotations

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTIFICATIONS_COMPOSE = (
    PROJECT_ROOT / "modules" / "notifications" / "docker-compose.yml"
)


def test_notifications_source_mount_requires_explicit_deployment_source() -> None:
    """Do not silently execute Notifications from a mutable host checkout."""
    compose = NOTIFICATIONS_COMPOSE.read_text(encoding="utf-8")

    assert "/opt/project-atlas:/opt/project-atlas:ro" not in compose

    source_mount = re.compile(
        r"\$\{ATLAS_NOTIFICATIONS_SOURCE_DIR:\?[^}]+\}"
        r":/opt/project-atlas:ro"
    )

    assert source_mount.search(compose), (
        "Notifications must mount an explicitly supplied deployment source "
        "read-only at its application root."
    )
