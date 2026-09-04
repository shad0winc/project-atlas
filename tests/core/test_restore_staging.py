from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tarfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECOVERY_LIBRARY = PROJECT_ROOT / "scripts" / "lib" / "backup-recovery.sh"
RESTORE_COMMAND = PROJECT_ROOT / "scripts" / "commands" / "restore.sh"


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
    ("sports-live-tv-bindings", "state/sports/live-tv-bindings.json", "required", "file", True),
    ("sports-source-lifecycle", "state/sports/source-lifecycle.json", "required", "file", True),
    ("sports-recordings", "state/sports/recordings.json", "required", "file", True),
    ("sports-scheduler", "state/sports/scheduler.json", "required", "file", True),
)


def _environment(tmp_path: Path) -> dict[str, str]:
    config_root = tmp_path / "source-configs"
    atlas_root = config_root / "atlas"
    return {
        **os.environ,
        "ATLAS_PROJECT_DIR": str(PROJECT_ROOT),
        "ATLAS_CONFIG_ROOT": str(config_root),
        "ATLAS_RUNTIME_CONFIG_DIR": str(atlas_root),
        "ATLAS_USERS_DIR": str(atlas_root / "users"),
        "ATLAS_IDENTITY_DIR": str(atlas_root / "identity"),
        "ATLAS_REQUESTS_DIR": str(atlas_root / "requests"),
        "ATLAS_SCHEDULER_STATE_FILE": str(atlas_root / "scheduler" / "tasks.json"),
        "ATLAS_ARI_DIR": str(atlas_root / "ari"),
        "SPORTS_CONFIG_DIR": str(config_root / "sportyfin"),
        "RECOVERY_LIBRARY": str(RECOVERY_LIBRARY),
        "RESTORE_COMMAND": str(RESTORE_COMMAND),
    }


def _add_text(archive: tarfile.TarFile, name: str, text: str) -> None:
    payload = text.encode()
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(payload))


def _build_archive(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    stage = tmp_path / "archive-source"
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
        "state/sports/live-tv-bindings.json": '{"version":1,"bindings":{}}\n',
        "state/sports/source-lifecycle.json": '{"version":1,"sources":[]}\n',
    }
    for relative, value in files.items():
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")

    (stage / "RECOVERY_FORMAT").write_text("1\n", encoding="utf-8")
    (stage / "BACKUP_INFO.txt").write_text(
        "Project Atlas Backup\nRecovery state: state-complete\n"
        "Recovery capability: restore-unverified\n",
        encoding="utf-8",
    )
    manifest = [
        "surface\tarchive_path\trequirement\tpolicy",
        "project-configuration\t.\trequired\tconfiguration-only",
    ]
    for surface, archive_path, requirement, _kind, captured in SURFACES:
        policy = "captured" if captured else "absent-optional"
        manifest.append(f"{surface}\t{archive_path}\t{requirement}\t{policy}")
    (stage / "RECOVERY_MANIFEST.tsv").write_text(
        "\n".join(manifest) + "\n", encoding="utf-8"
    )
    checksums = []
    for item in sorted((stage / "state").rglob("*")):
        if item.is_file():
            relative = item.relative_to(stage).as_posix()
            checksums.append(f"{hashlib.sha256(item.read_bytes()).hexdigest()}  {relative}")
    (stage / "SHA256SUMS").write_text(
        "\n".join(checksums) + "\n", encoding="utf-8"
    )
    (stage / "VERSION").write_text("test\n", encoding="utf-8")

    archive_path = tmp_path / "valid.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name in (
            "BACKUP_INFO.txt",
            "RECOVERY_FORMAT",
            "RECOVERY_MANIFEST.tsv",
            "SHA256SUMS",
            "VERSION",
            "state",
        ):
            archive.add(stage / name, arcname=name, recursive=True)
    return archive_path, env


def _stage(
    archive: Path,
    parent: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$RECOVERY_LIBRARY"; '
            'atlas_backup_recovery_stage_archive "$ARCHIVE" "$PARENT"',
        ],
        cwd=PROJECT_ROOT,
        env={**env, "ARCHIVE": str(archive), "PARENT": str(parent)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_valid_archive_stages_into_new_private_root(tmp_path: Path) -> None:
    archive, env = _build_archive(tmp_path)
    parent = tmp_path / "staging"
    parent.mkdir()

    result = _stage(archive, parent, env)

    assert result.returncode == 0, result.stderr
    staged = Path(result.stdout.strip())
    try:
        assert staged.parent == parent
        assert staged.name.startswith("project-atlas-restore.")
        assert staged.stat().st_mode & 0o777 == 0o700
        assert (staged / "state/users/users.json").read_text() == "users-v1\n"
        assert (staged / "state/users/users.json").stat().st_mode & 0o777 == 0o600
        assert not (staged / "state/identity/invitations").exists()
        assert not (staged / "state/requests/requests.json").exists()
    finally:
        subprocess.run(["rm", "-rf", "--", str(staged)], check=False)


def test_stage_rejects_parent_symlink(tmp_path: Path) -> None:
    archive, env = _build_archive(tmp_path)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)

    result = _stage(archive, linked_parent, env)

    assert result.returncode != 0
    assert "absolute real directory" in result.stderr
    assert list(real_parent.iterdir()) == []


def _unsafe_archive(
    tmp_path: Path,
    *,
    name: str,
    kind: str = "file",
) -> Path:
    path = tmp_path / f"unsafe-{kind}.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        if kind == "file":
            _add_text(archive, name, "unsafe\n")
        elif kind == "symlink":
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            archive.addfile(info)
        elif kind == "hardlink":
            info = tarfile.TarInfo(name)
            info.type = tarfile.LNKTYPE
            info.linkname = "RECOVERY_FORMAT"
            archive.addfile(info)
    return path


def _safe_members(archive: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$RECOVERY_LIBRARY"; '
            'atlas_backup_recovery_validate_safe_members "$ARCHIVE"',
        ],
        cwd=PROJECT_ROOT,
        env={
            **os.environ,
            "ARCHIVE": str(archive),
            "RECOVERY_LIBRARY": str(RECOVERY_LIBRARY),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_member_safety_rejects_absolute_path(tmp_path: Path) -> None:
    result = _safe_members(_unsafe_archive(tmp_path, name="/tmp/escape"))
    assert result.returncode != 0
    assert "unsafe recovery archive member path" in result.stderr


def test_member_safety_rejects_parent_traversal(tmp_path: Path) -> None:
    result = _safe_members(_unsafe_archive(tmp_path, name="state/../escape"))
    assert result.returncode != 0
    assert "unsafe recovery archive member path" in result.stderr


def test_member_safety_rejects_undeclared_top_level(tmp_path: Path) -> None:
    result = _safe_members(_unsafe_archive(tmp_path, name="unexpected/file"))
    assert result.returncode != 0
    assert "undeclared recovery archive member" in result.stderr


def test_member_safety_rejects_symbolic_link(tmp_path: Path) -> None:
    result = _safe_members(
        _unsafe_archive(tmp_path, name="state/users/link", kind="symlink")
    )
    assert result.returncode != 0
    assert "unsupported recovery archive member type" in result.stderr


def test_member_safety_rejects_hard_link(tmp_path: Path) -> None:
    result = _safe_members(
        _unsafe_archive(tmp_path, name="state/users/link", kind="hardlink")
    )
    assert result.returncode != 0
    assert "unsupported recovery archive member type" in result.stderr


def test_public_stage_command_uses_tmp_and_preserves_live_boundary(
    tmp_path: Path,
) -> None:
    archive, env = _build_archive(tmp_path)
    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; atlas_print_header() { :; }; '
            'source "$RESTORE_COMMAND"; atlas_command_restore stage "$ARCHIVE"',
        ],
        cwd=PROJECT_ROOT,
        env={
            **env,
            "ARCHIVE": str(archive),
            "RESTORE_COMMAND": str(RESTORE_COMMAND),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Atlas Restore Staging: PASS" in result.stdout
    assert "Live state mutation: none" in result.stdout
    staging_line = next(
        line for line in result.stdout.splitlines() if line.startswith("Staging root: ")
    )
    staged = Path(staging_line.removeprefix("Staging root: "))
    try:
        assert staged.parent == Path("/tmp")
        assert (staged / "state/scheduler/tasks.json").is_file()
    finally:
        subprocess.run(["rm", "-rf", "--", str(staged)], check=False)


def test_live_apply_requires_explicit_confirmation() -> None:
    content = RESTORE_COMMAND.read_text(encoding="utf-8")
    assert "restore apply requires <staging-root> --confirm-live" in content
    assert "atlas_restore_apply_live()" in content
    assert "atlas_restore_resume_live()" in content
    assert "atlas_restore_abort_live()" in content
    assert "atlas_backup_recovery_stage_archive" in content


def _restore_plan(
    root: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$RECOVERY_LIBRARY"; '
            'atlas_backup_recovery_restore_plan "$STAGE_ROOT"',
        ],
        cwd=PROJECT_ROOT,
        env={**env, "STAGE_ROOT": str(root)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_restore_plan_maps_only_declared_surfaces(tmp_path: Path) -> None:
    archive, env = _build_archive(tmp_path)
    parent = tmp_path / "staging"
    parent.mkdir()
    staged_result = _stage(archive, parent, env)
    assert staged_result.returncode == 0, staged_result.stderr
    staged = Path(staged_result.stdout.strip())

    try:
        result = _restore_plan(staged, env)

        assert result.returncode == 0, result.stderr
        rows = [line.split("\t") for line in result.stdout.splitlines() if line]
        assert len(rows) == 13
        by_surface = {row[0]: row for row in rows}
        assert set(by_surface) == {surface for surface, *_ in SURFACES}
        assert by_surface["users"][1] == "replace"
        assert by_surface["users"][2] == "directory"
        assert by_surface["identity-invitations"][1] == "remove-if-present"
        assert by_surface["requests"][1] == "remove-if-present"
        assert by_surface["runtime-events"][3] == "runtime-events"
        assert by_surface["runtime-subscribers"][3] == "runtime-events"
        assert by_surface["sports-recordings"][3] == "sports"
        assert by_surface["sports-live-tv-bindings"][3] == "sports"
        assert by_surface["users"][5] == env["ATLAS_USERS_DIR"]
        assert by_surface["scheduler"][5] == env["ATLAS_SCHEDULER_STATE_FILE"]
        assert all(row[5].startswith(env["ATLAS_CONFIG_ROOT"] + "/") for row in rows)
    finally:
        subprocess.run(["rm", "-rf", "--", str(staged)], check=False)


def test_restore_plan_rejects_symbolic_destination_ancestor(tmp_path: Path) -> None:
    archive, env = _build_archive(tmp_path)
    parent = tmp_path / "staging"
    parent.mkdir()
    staged_result = _stage(archive, parent, env)
    assert staged_result.returncode == 0, staged_result.stderr
    staged = Path(staged_result.stdout.strip())

    config_root = Path(env["ATLAS_CONFIG_ROOT"])
    config_root.mkdir(parents=True, exist_ok=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (config_root / "atlas").symlink_to(elsewhere, target_is_directory=True)

    try:
        result = _restore_plan(staged, env)
        assert result.returncode != 0
        assert "symbolic link" in result.stderr
    finally:
        subprocess.run(["rm", "-rf", "--", str(staged)], check=False)
