from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PROJECT_ROOT / "scripts" / "lib" / "validate-recovery-state.py"
RESTORE_COMMAND = PROJECT_ROOT / "scripts" / "commands" / "restore.sh"


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


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _staged_root(tmp_path: Path) -> Path:
    root = tmp_path / "stage"
    manifest = ["surface\tarchive_path\trequirement\tpolicy"]
    manifest.append("project-configuration\t.\trequired\tconfiguration-only")
    manifest.extend("\t".join(row) for row in SURFACES)
    root.mkdir()
    (root / "RECOVERY_MANIFEST.tsv").write_text("\n".join(manifest) + "\n", encoding="utf-8")

    _write_json(root / "state/users/users.json", {"schema_version": 1, "users": {}})
    _write_json(
        root / "state/identity/favorites/favorites.json",
        {"schema_version": 1, "favorites": {}},
    )
    _write_json(
        root / "state/scheduler/tasks.json",
        {"schema_version": 2, "tasks": {}, "history": []},
    )
    events = root / "state/runtime/events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text("", encoding="utf-8")
    subscribers = root / "state/runtime/subscribers"
    subscribers.mkdir()
    (subscribers / "test.cursor").write_text("0\n", encoding="utf-8")
    (subscribers / "test.filter").write_text("*\n", encoding="utf-8")
    (root / "state/retention").mkdir(parents=True)
    _write_json(root / "state/sports/subscriptions.json", {"subscriptions": []})
    _write_json(root / "state/sports/recordings.json", {})
    _write_json(root / "state/sports/scheduler.json", {})
    return root


def _snapshot(root: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            result[relative] = (
                path.stat().st_mode & 0o777,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        elif path.is_dir():
            result[relative] = (path.stat().st_mode & 0o777, "directory")
    return result


def _validate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", str(VALIDATOR), str(root), str(PROJECT_ROOT)],
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_consumer_validation_accepts_structurally_valid_state(tmp_path: Path) -> None:
    root = _staged_root(tmp_path)
    before = _snapshot(root)

    result = _validate(root)

    assert result.returncode == 0, result.stderr
    assert "PASS users" in result.stdout
    assert "PASS favorites" in result.stdout
    assert "PASS scheduler" in result.stdout
    assert "PASS runtime" in result.stdout
    assert "PASS retention" in result.stdout
    assert "PASS sports-subscriptions" in result.stdout
    assert "PASS sports-recordings" in result.stdout
    assert "PASS sports-scheduler" in result.stdout
    assert "SKIP identity-invitations" in result.stdout
    assert "SKIP requests" in result.stdout
    assert _snapshot(root) == before


def test_consumer_validation_accepts_empty_request_registry(tmp_path: Path) -> None:
    root = _staged_root(tmp_path)
    manifest = root / "RECOVERY_MANIFEST.tsv"
    content = manifest.read_text(encoding="utf-8")
    manifest.write_text(
        content.replace(
            "requests\tstate/requests/requests.json\toptional\tabsent-optional",
            "requests\tstate/requests/requests.json\toptional\tcaptured",
        ),
        encoding="utf-8",
    )
    _write_json(
        root / "state/requests/requests.json",
        {"schema_version": 1, "requests": {}},
    )

    result = _validate(root)

    assert result.returncode == 0, result.stderr
    assert "PASS requests" in result.stdout


def test_consumer_validation_rejects_invalid_user_registry(tmp_path: Path) -> None:
    root = _staged_root(tmp_path)
    _write_json(root / "state/users/users.json", {"schema_version": 1, "users": []})
    result = _validate(root)
    assert result.returncode != 0
    assert "staged recovery consumer validation failed" in result.stderr


def test_consumer_validation_rejects_cursor_beyond_event_journal(tmp_path: Path) -> None:
    root = _staged_root(tmp_path)
    (root / "state/runtime/subscribers/test.cursor").write_text("1\n", encoding="utf-8")
    result = _validate(root)
    assert result.returncode != 0
    assert "subscriber cursor exceeds journal" in result.stderr


def test_consumer_validation_rejects_invalid_sports_subscription(tmp_path: Path) -> None:
    root = _staged_root(tmp_path)
    _write_json(
        root / "state/sports/subscriptions.json",
        {"subscriptions": [{"type": "invalid", "provider": "x", "id": "1"}]},
    )
    result = _validate(root)
    assert result.returncode != 0


def test_validate_stage_command_rejects_non_isolated_root(tmp_path: Path) -> None:
    command = f"""
set -euo pipefail
atlas_print_header() {{ :; }}
source {str(RESTORE_COMMAND)!r}
atlas_command_restore validate-stage {str(tmp_path)!r}
"""
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "isolated /tmp staging root" in result.stderr


def test_consumer_validation_preserves_legacy_ari_history(tmp_path: Path) -> None:
    root = _staged_root(tmp_path)
    history = root / "state/retention/snapshots/legacy.json"
    history.parent.mkdir(parents=True)
    history.write_text('{"legacy": true}\n', encoding="utf-8")
    before = _snapshot(root)

    result = _validate(root)

    assert result.returncode == 0, result.stderr
    assert "PASS retention" in result.stdout
    assert "1 legacy/incompatible skipped" in result.stdout
    assert _snapshot(root) == before


def test_consumer_validation_rejects_invalid_current_ari_state(tmp_path: Path) -> None:
    root = _staged_root(tmp_path)
    latest = root / "state/retention/latest.json"
    latest.write_text('{"legacy": true}\n', encoding="utf-8")

    result = _validate(root)

    assert result.returncode != 0
    assert "staged recovery consumer validation failed" in result.stderr
    assert "Traceback" not in result.stderr
