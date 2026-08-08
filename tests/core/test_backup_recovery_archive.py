from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = PROJECT_ROOT / "scripts" / "lib" / "backup-recovery.sh"


def _environment(tmp_path: Path) -> dict[str, str]:
    config_root = tmp_path / "configs"
    atlas_root = config_root / "atlas"
    return {
        **os.environ,
        "ATLAS_CONFIG_ROOT": str(config_root),
        "ATLAS_RUNTIME_CONFIG_DIR": str(atlas_root),
        "ATLAS_USERS_DIR": str(atlas_root / "users"),
        "ATLAS_IDENTITY_DIR": str(atlas_root / "identity"),
        "ATLAS_REQUESTS_DIR": str(atlas_root / "requests"),
        "ATLAS_SCHEDULER_STATE_FILE": str(atlas_root / "scheduler" / "tasks.json"),
        "ATLAS_ARI_DIR": str(atlas_root / "ari"),
        "SPORTS_CONFIG_DIR": str(config_root / "sportyfin"),
        "REGISTRY": str(REGISTRY),
    }


SURFACES = (
    ("users", "state/users", "required", "directory", True),
    ("identity-invitations", "state/identity/invitations", "optional", "directory", False),
    ("favorites", "state/identity/favorites", "required", "directory", True),
    ("requests", "state/requests/requests.json", "optional", "file", False),
    ("scheduler", "state/scheduler/tasks.json", "required", "file", True),
    ("runtime-events", "state/runtime/events.jsonl", "required", "file", True),
    ("runtime-subscribers", "state/runtime/subscribers", "required", "directory", True),
    ("retention", "state/retention", "required", "directory", True),
    ("sports-subscriptions", "state/sports/subscriptions.json", "required", "file", True),
    ("sports-recordings", "state/sports/recordings.json", "required", "file", True),
    ("sports-scheduler", "state/sports/scheduler.json", "required", "file", True),
)


def _build_archive(
    tmp_path: Path,
    *,
    corrupt_after_checksums: bool = False,
    omit_scheduler: bool = False,
) -> tuple[Path, dict[str, str]]:
    stage = tmp_path / "stage"
    stage.mkdir()
    env = _environment(tmp_path)

    files = {
        "state/users/users.json": "users-v1\n",
        "state/identity/favorites/favorites.json": "favorites-v1\n",
        "state/scheduler/tasks.json": "scheduler-v1\n",
        "state/runtime/events.jsonl": "event-v1\n",
        "state/runtime/subscribers/user.cursor": "1\n",
        "state/retention/state.json": "retention-v1\n",
        "state/sports/subscriptions.json": "subscriptions-v1\n",
        "state/sports/recordings.json": "recordings-v1\n",
        "state/sports/scheduler.json": "sports-scheduler-v1\n",
    }

    if omit_scheduler:
        files.pop("state/scheduler/tasks.json")

    for relative, value in files.items():
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    (stage / "RECOVERY_FORMAT").write_text("1\n", encoding="utf-8")
    (stage / "BACKUP_INFO.txt").write_text(
        "Project Atlas Backup\n\n"
        "Recovery format: 1\n"
        "Recovery state: state-complete\n"
        "Recovery capability: restore-unverified\n",
        encoding="utf-8",
    )

    manifest = [
        "surface\tarchive_path\trequirement\tpolicy",
        "project-configuration\t.\trequired\tconfiguration-only",
    ]
    for surface, archive_path, requirement, _kind, captured in SURFACES:
        policy = "captured" if captured else "absent-optional"
        manifest.append(
            f"{surface}\t{archive_path}\t{requirement}\t{policy}"
        )
    (stage / "RECOVERY_MANIFEST.tsv").write_text(
        "\n".join(manifest) + "\n",
        encoding="utf-8",
    )

    checksum_lines = []
    for state_file in sorted((stage / "state").rglob("*")):
        if not state_file.is_file():
            continue
        relative = state_file.relative_to(stage).as_posix()
        digest = hashlib.sha256(state_file.read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {relative}")
    (stage / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )

    if corrupt_after_checksums:
        (stage / "state/runtime/events.jsonl").write_text(
            "event-corrupted\n",
            encoding="utf-8",
        )

    archive = tmp_path / "backup.tar.gz"
    result = subprocess.run(
        [
            "tar",
            "-czf",
            str(archive),
            "-C",
            str(stage),
            "BACKUP_INFO.txt",
            "RECOVERY_FORMAT",
            "RECOVERY_MANIFEST.tsv",
            "SHA256SUMS",
            "state",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return archive, env


def _validate(archive: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    environment = {**env, "ARCHIVE": str(archive)}
    return subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$REGISTRY"; '
            'atlas_backup_recovery_validate_archive "$ARCHIVE"',
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_state_complete_archive_passes_integrity_validation(tmp_path: Path) -> None:
    archive, env = _build_archive(tmp_path)

    result = _validate(archive, env)

    assert result.returncode == 0, result.stderr


def test_archive_rejects_checksum_mismatch(tmp_path: Path) -> None:
    archive, env = _build_archive(tmp_path, corrupt_after_checksums=True)

    result = _validate(archive, env)

    assert result.returncode != 0
    assert "recovery checksum mismatch" in result.stderr


def test_archive_rejects_missing_required_surface(tmp_path: Path) -> None:
    archive, env = _build_archive(tmp_path, omit_scheduler=True)

    result = _validate(archive, env)

    assert result.returncode != 0
    assert "captured recovery surface is absent: scheduler" in result.stderr


def test_archive_keeps_restore_capability_unverified() -> None:
    content = (PROJECT_ROOT / "scripts" / "commands" / "backup.sh").read_text(
        encoding="utf-8"
    )

    assert "Recovery state: state-complete" in content
    assert "Recovery capability: restore-unverified" in content
    assert "state-complete; restore-unverified" in content
    assert "restore-verified" not in content
