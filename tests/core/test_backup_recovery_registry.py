from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = PROJECT_ROOT / "scripts" / "lib" / "backup-recovery.sh"
ATLAS_CONFIG = PROJECT_ROOT / "config" / "atlas.conf"


def _environment(tmp_path: Path) -> dict[str, str]:
    runtime = tmp_path / "atlas"
    config_root = tmp_path / "configs"

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_CONFIG_ROOT": str(config_root),
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
            "ATLAS_USERS_DIR": str(runtime / "users"),
            "ATLAS_IDENTITY_DIR": str(runtime / "identity"),
            "ATLAS_REQUESTS_DIR": str(runtime / "requests"),
            "ATLAS_SCHEDULER_STATE_FILE": str(runtime / "scheduler" / "tasks.json"),
            "ATLAS_ARI_DIR": str(runtime / "ari"),
        }
    )
    return environment


def _rows(tmp_path: Path) -> list[list[str]]:
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$REGISTRY"; atlas_backup_recovery_surface_rows',
        ],
        env={**_environment(tmp_path), "REGISTRY": str(REGISTRY)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [line.split("\t") for line in result.stdout.splitlines()]


def test_registry_is_structurally_valid(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$REGISTRY"; '
                "atlas_backup_recovery_validate_registry"
            ),
        ],
        env={**_environment(tmp_path), "REGISTRY": str(REGISTRY)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_registry_declares_exact_recovery_surfaces(tmp_path: Path) -> None:
    rows = _rows(tmp_path)
    assert len(rows) == 11
    assert all(len(row) == 6 for row in rows)

    assert [row[0] for row in rows] == [
        "users",
        "identity-invitations",
        "favorites",
        "requests",
        "scheduler",
        "runtime-events",
        "runtime-subscribers",
        "retention",
        "sports-subscriptions",
        "sports-recordings",
        "sports-scheduler",
    ]


def test_request_surface_is_explicit_and_optional(tmp_path: Path) -> None:
    rows = {row[0]: row for row in _rows(tmp_path)}
    request = rows["requests"]

    assert request[1].endswith("/atlas/requests/requests.json")
    assert request[2] == "state/requests/requests.json"
    assert request[3] == "optional"
    assert request[4] == "file"
    assert request[5] == "requests"


def test_runtime_event_state_shares_one_consistency_group(
    tmp_path: Path,
) -> None:
    rows = {row[0]: row for row in _rows(tmp_path)}

    assert rows["runtime-events"][5] == "runtime-events"
    assert rows["runtime-subscribers"][5] == "runtime-events"


def test_sports_registry_excludes_reconstructible_runtime_files(
    tmp_path: Path,
) -> None:
    rows = _rows(tmp_path)
    serialized = "\n".join("\t".join(row) for row in rows)

    assert "subscriptions.json" in serialized
    assert "recordings.json" in serialized
    assert "scheduler.json" in serialized
    assert "health.json" not in serialized
    assert "controller-heartbeat" not in serialized
    assert "sports.m3u" not in serialized
    assert "sports.xml" not in serialized
    assert "/logs/" not in serialized


def test_process_locks_are_not_recovery_surfaces(tmp_path: Path) -> None:
    serialized = "\n".join("\t".join(row) for row in _rows(tmp_path))

    assert "scheduler.lock" not in serialized
    assert "update.lock" not in serialized
    assert "maintenance/enabled" not in serialized


def test_atlas_config_defines_canonical_request_root() -> None:
    content = ATLAS_CONFIG.read_text(encoding="utf-8")

    assert (
        'ATLAS_REQUESTS_DIR="${ATLAS_RUNTIME_CONFIG_DIR}/requests"'
        in content
    )
