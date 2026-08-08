from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECOVERY_LIBRARY = PROJECT_ROOT / "scripts" / "lib" / "backup-recovery.sh"

SURFACES = (
    ("users", "state/users", "required", "captured"),
    ("identity-invitations", "state/identity/invitations", "optional", "absent-optional"),
    ("favorites", "state/identity/favorites", "required", "captured"),
    ("requests", "state/requests/requests.json", "optional", "absent-optional"),
    ("scheduler", "state/scheduler/tasks.json", "required", "captured"),
    ("runtime-events", "state/runtime/events.jsonl", "required", "captured"),
    ("runtime-subscribers", "state/runtime/subscribers", "required", "captured"),
    ("retention", "state/retention", "required", "captured"),
    ("sports-subscriptions", "state/sports/subscriptions.json", "required", "captured"),
    ("sports-recordings", "state/sports/recordings.json", "required", "captured"),
    ("sports-scheduler", "state/sports/scheduler.json", "required", "captured"),
)


def _environment(tmp_path: Path) -> dict[str, str]:
    config = tmp_path / "configs"
    atlas = config / "atlas"
    return {
        **os.environ,
        "ATLAS_PROJECT_DIR": str(PROJECT_ROOT),
        "ATLAS_CONFIG_ROOT": str(config),
        "ATLAS_RUNTIME_CONFIG_DIR": str(atlas),
        "ATLAS_USERS_DIR": str(atlas / "users"),
        "ATLAS_IDENTITY_DIR": str(atlas / "identity"),
        "ATLAS_REQUESTS_DIR": str(atlas / "requests"),
        "ATLAS_SCHEDULER_STATE_FILE": str(atlas / "scheduler" / "tasks.json"),
        "ATLAS_ARI_DIR": str(atlas / "ari"),
        "SPORTS_CONFIG_DIR": str(config / "sportyfin"),
        "RECOVERY_LIBRARY": str(RECOVERY_LIBRARY),
    }


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _stage(tmp_path: Path) -> Path:
    root = tmp_path / "stage"
    root.mkdir()
    files = {
        "state/users/users.json": "new-users\n",
        "state/identity/favorites/favorites.json": "new-favorites\n",
        "state/scheduler/tasks.json": "new-scheduler\n",
        "state/runtime/events.jsonl": "new-event\n",
        "state/runtime/subscribers/test.cursor": "1\n",
        "state/retention/latest.json": "new-retention\n",
        "state/sports/subscriptions.json": "new-subscriptions\n",
        "state/sports/recordings.json": "new-recordings\n",
        "state/sports/scheduler.json": "new-sports-scheduler\n",
    }
    for relative, value in files.items():
        _write(root / relative, value)

    _write(root / "RECOVERY_FORMAT", "1\n")
    _write(root / "BACKUP_INFO.txt", "Project Atlas Backup\n")
    manifest = [
        "surface\tarchive_path\trequirement\tpolicy",
        "project-configuration\t.\trequired\tconfiguration-only",
    ]
    manifest.extend("\t".join(row) for row in SURFACES)
    _write(root / "RECOVERY_MANIFEST.tsv", "\n".join(manifest) + "\n")

    checksums = []
    for item in sorted((root / "state").rglob("*")):
        if item.is_file():
            relative = item.relative_to(root).as_posix()
            digest = hashlib.sha256(item.read_bytes()).hexdigest()
            checksums.append(f"{digest}  {relative}")
    _write(root / "SHA256SUMS", "\n".join(checksums) + "\n")
    return root


def _destinations(env: dict[str, str]) -> dict[str, Path]:
    atlas = Path(env["ATLAS_RUNTIME_CONFIG_DIR"])
    sports = Path(env["SPORTS_CONFIG_DIR"])
    return {
        "users": Path(env["ATLAS_USERS_DIR"]),
        "identity-invitations": Path(env["ATLAS_IDENTITY_DIR"]) / "invitations",
        "favorites": Path(env["ATLAS_IDENTITY_DIR"]) / "favorites",
        "requests": Path(env["ATLAS_REQUESTS_DIR"]) / "requests.json",
        "scheduler": Path(env["ATLAS_SCHEDULER_STATE_FILE"]),
        "runtime-events": atlas / "runtime/events.jsonl",
        "runtime-subscribers": atlas / "runtime/subscribers",
        "retention": Path(env["ATLAS_ARI_DIR"]),
        "sports-subscriptions": sports / "state/subscriptions.json",
        "sports-recordings": sports / "recordings/recordings.json",
        "sports-scheduler": atlas / "runtime/scheduler/sports.json",
    }


def _populate_live(env: dict[str, str]) -> dict[str, Path]:
    destinations = _destinations(env)
    directory_files = {
        "users": "users.json",
        "identity-invitations": "invite.json",
        "favorites": "favorites.json",
        "runtime-subscribers": "test.cursor",
        "retention": "latest.json",
    }
    for surface, destination in destinations.items():
        if surface in directory_files:
            _write(destination / directory_files[surface], f"old-{surface}\n")
        else:
            _write(destination, f"old-{surface}\n")
    return destinations


def _tree(path: Path) -> tuple[str, tuple[tuple[str, str], ...]]:
    if not path.exists():
        return ("absent", ())
    if path.is_file():
        return ("file", ((".", path.read_text(encoding="utf-8")),))
    rows = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            rows.append((item.relative_to(path).as_posix(), item.read_text(encoding="utf-8")))
    return ("directory", tuple(rows))


def _surface_snapshot(destinations: dict[str, Path]) -> dict[str, object]:
    return {surface: _tree(path) for surface, path in destinations.items()}


def _stage_snapshot(root: Path) -> dict[str, str]:
    result = {}
    for item in sorted(root.rglob("*")):
        if item.is_file():
            result[item.relative_to(root).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def _run(
    env: dict[str, str],
    stage: Path,
    transaction: Path,
    *,
    fail_after: str | None = None,
    finalize: bool = False,
) -> subprocess.CompletedProcess[str]:
    hook = ""
    if fail_after is not None:
        hook = (
            "\natlas_backup_recovery_after_surface_apply() {\n"
            f'  [[ "$1" != {fail_after!r} ]]\n'
            "}\n"
        )
    command = f'''
set -euo pipefail
source "$RECOVERY_LIBRARY"
{hook}
atlas_backup_recovery_apply_staged_state "$STAGE_ROOT" "$TRANSACTION_ROOT"
'''
    if finalize:
        command += 'atlas_backup_recovery_finalize_applied_state "$TRANSACTION_ROOT"\n'
    return subprocess.run(
        ["bash", "-c", command],
        cwd=PROJECT_ROOT,
        env={
            **env,
            "STAGE_ROOT": str(stage),
            "TRANSACTION_ROOT": str(transaction),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_bounded_application_replaces_declared_state_and_can_revert(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    stage = _stage(tmp_path)
    destinations = _populate_live(env)
    before = _surface_snapshot(destinations)
    staged_before = _stage_snapshot(stage)
    transaction = Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "restores/test-success"

    result = _run(env, stage, transaction)
    assert result.returncode == 0, result.stderr
    assert (transaction / "status").read_text().strip() == "applied-awaiting-verification"
    assert _tree(destinations["users"])[1][0][1] == "new-users\n"
    assert not destinations["identity-invitations"].exists()
    assert not destinations["requests"].exists()
    assert _stage_snapshot(stage) == staged_before

    revert = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$RECOVERY_LIBRARY"; '
            'atlas_backup_recovery_revert_applied_state "$TRANSACTION_ROOT"',
        ],
        cwd=PROJECT_ROOT,
        env={**env, "TRANSACTION_ROOT": str(transaction)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert revert.returncode == 0, revert.stderr
    assert _surface_snapshot(destinations) == before
    assert (transaction / "status").read_text().strip() == "reverted"


def test_mid_transaction_failure_reverts_every_applied_surface(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    stage = _stage(tmp_path)
    destinations = _populate_live(env)
    before = _surface_snapshot(destinations)
    transaction = Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "restores/test-failure"

    result = _run(env, stage, transaction, fail_after="scheduler")

    assert result.returncode != 0
    assert "interrupted after surface: scheduler" in result.stderr
    assert _surface_snapshot(destinations) == before
    assert (transaction / "status").read_text().strip() == "reverted"


def test_finalize_discards_local_displacement_only_after_success(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    stage = _stage(tmp_path)
    destinations = _populate_live(env)
    transaction = Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "restores/test-finalize"

    result = _run(env, stage, transaction, finalize=True)

    assert result.returncode == 0, result.stderr
    assert (transaction / "status").read_text().strip() == "verified"
    assert not (transaction / "live-rollback").exists()
    assert _tree(destinations["users"])[1][0][1] == "new-users\n"
    assert not destinations["identity-invitations"].exists()
    assert not destinations["requests"].exists()


def test_application_preserves_unrelated_configuration(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    stage = _stage(tmp_path)
    _populate_live(env)
    unrelated = Path(env["ATLAS_CONFIG_ROOT"]) / "unrelated/keep.txt"
    _write(unrelated, "keep-me\n")
    transaction = Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "restores/test-unrelated"

    result = _run(env, stage, transaction)

    assert result.returncode == 0, result.stderr
    assert unrelated.read_text(encoding="utf-8") == "keep-me\n"


def test_application_rejects_transaction_outside_config_root(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    stage = _stage(tmp_path)
    _populate_live(env)
    transaction = tmp_path / "outside-transaction"

    result = _run(env, stage, transaction)

    assert result.returncode != 0
    assert "outside Atlas configuration" in result.stderr
