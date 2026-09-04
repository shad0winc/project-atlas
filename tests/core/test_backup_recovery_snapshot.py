from __future__ import annotations

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


def _write_state(tmp_path: Path) -> dict[str, str]:
    env = _environment(tmp_path)

    live_tv_bindings = (
        Path(env["SPORTS_CONFIG_DIR"])
        / "state"
        / "live-tv-bindings.json"
    )
    live_tv_bindings.parent.mkdir(parents=True, exist_ok=True)
    live_tv_bindings.write_text(
        '{"version":1,"bindings":{}}\n',
        encoding="utf-8",
    )

    paths = {
        "users": Path(env["ATLAS_USERS_DIR"]) / "users.json",
        "favorites": Path(env["ATLAS_IDENTITY_DIR"]) / "favorites" / "favorites.json",
        "scheduler": Path(env["ATLAS_SCHEDULER_STATE_FILE"]),
        "events": Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "runtime" / "events.jsonl",
        "cursor": Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "runtime" / "subscribers" / "user.cursor",
        "retention": Path(env["ATLAS_ARI_DIR"]) / "state.json",
        "subscriptions": Path(env["SPORTS_CONFIG_DIR"]) / "state" / "subscriptions.json",
        "recordings": Path(env["SPORTS_CONFIG_DIR"]) / "recordings" / "recordings.json",
        "sports_scheduler": Path(env["ATLAS_RUNTIME_CONFIG_DIR"]) / "runtime" / "scheduler" / "sports.json",
    }

    for name, state_path in paths.items():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(f"{name}-v1\n", encoding="utf-8")

    return env


def _snapshot(
    tmp_path: Path,
    *,
    shell_suffix: str = "",
) -> subprocess.CompletedProcess[str]:
    env = _write_state(tmp_path)
    destination = tmp_path / "snapshot"
    env["DESTINATION"] = str(destination)

    command = f'''
set -euo pipefail
source "$REGISTRY"
{shell_suffix}
atlas_backup_recovery_snapshot_state "$DESTINATION"
'''

    return subprocess.run(
        ["bash", "-c", command],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_snapshot_captures_every_required_surface(tmp_path: Path) -> None:
    result = _snapshot(tmp_path)

    assert result.returncode == 0, result.stderr
    destination = tmp_path / "snapshot"

    required = (
        "state/users/users.json",
        "state/identity/favorites/favorites.json",
        "state/scheduler/tasks.json",
        "state/runtime/events.jsonl",
        "state/runtime/subscribers/user.cursor",
        "state/retention/state.json",
        "state/sports/subscriptions.json",
        "state/sports/live-tv-bindings.json",
        "state/sports/recordings.json",
        "state/sports/scheduler.json",
    )

    for relative in required:
        assert (destination / relative).is_file(), relative

    assert "requests\tstate/requests/requests.json\toptional\tabsent-optional" in result.stdout
    assert "identity-invitations\tstate/identity/invitations\toptional\tabsent-optional" in result.stdout


def test_snapshot_retries_whole_group_when_source_changes(tmp_path: Path) -> None:
    shell_suffix = r'''
atlas_backup_recovery_after_group_copy() {
  local group="$1"
  if [[ "$group" == 'runtime-events' && ! -e "$DESTINATION.changed" ]]; then
    printf 'events-v2\n' > "$ATLAS_RUNTIME_CONFIG_DIR/runtime/events.jsonl"
    printf '1\n' > "$ATLAS_RUNTIME_CONFIG_DIR/runtime/subscribers/user.cursor"
    : > "$DESTINATION.changed"
  fi
}
'''
    result = _snapshot(tmp_path, shell_suffix=shell_suffix)

    assert result.returncode == 0, result.stderr
    assert "recovery consistency group changed during snapshot" in result.stderr

    destination = tmp_path / "snapshot"
    assert (destination / "state/runtime/events.jsonl").read_text() == "events-v2\n"
    assert (destination / "state/runtime/subscribers/user.cursor").read_text() == "1\n"


def test_snapshot_fails_closed_when_required_surface_is_missing(
    tmp_path: Path,
) -> None:
    env = _write_state(tmp_path)
    Path(env["ATLAS_SCHEDULER_STATE_FILE"]).unlink()
    env["DESTINATION"] = str(tmp_path / "snapshot")

    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$REGISTRY"; '
            'atlas_backup_recovery_snapshot_state "$DESTINATION"',
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "required recovery surface is unavailable: scheduler" in result.stderr


def test_snapshot_rejects_symbolic_links(tmp_path: Path) -> None:
    env = _write_state(tmp_path)
    users = Path(env["ATLAS_USERS_DIR"])
    (users / "unsafe-link").symlink_to(users / "users.json")
    env["DESTINATION"] = str(tmp_path / "snapshot")

    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$REGISTRY"; '
            'atlas_backup_recovery_snapshot_state "$DESTINATION"',
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "contains symbolic link" in result.stderr


def test_backup_command_packages_staged_state_without_claiming_completeness() -> None:
    content = (PROJECT_ROOT / "scripts" / "commands" / "backup.sh").read_text(
        encoding="utf-8"
    )

    assert 'atlas_backup_recovery_snapshot_state "$snapshot_root"' in content
    assert '-C "$snapshot_root" \\\n    state' in content
    assert "Recovery state: state-complete" in content
    assert "Recovery capability: restore-unverified" in content
    assert "state-complete; restore-unverified" in content
