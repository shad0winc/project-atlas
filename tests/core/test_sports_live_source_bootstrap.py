"""First-deployment bootstrap contract for Sports live-source state."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/lib/sports-live-source-bootstrap.sh"
UPDATE = ROOT / "scripts/commands/update.sh"


def _run(
    path: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()

    environment["ATLAS_PROJECT_DIR"] = str(ROOT)
    environment["ATLAS_SPORTS_LIVE_SOURCE_PATH"] = str(path)
    environment["ATLAS_SPORTS_LIVE_SOURCE_UID"] = str(os.geteuid())
    environment["ATLAS_SPORTS_LIVE_SOURCE_GID"] = str(os.getegid())

    return subprocess.run(
        [
            "bash",
            "-c",
            f'''
set -euo pipefail
source "{HELPER}"
atlas_sports_live_source_bootstrap_provision
''',
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_helper_exists() -> None:
    assert HELPER.is_file()


def test_helper_uses_canonical_writer_contract() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "/mnt/storage/configs/sportyfin/state/live-sources.json" in source
    assert 'ATLAS_SPORTS_LIVE_SOURCE_UID="${ATLAS_SPORTS_LIVE_SOURCE_UID:-1000}"' in source
    assert 'ATLAS_SPORTS_LIVE_SOURCE_GID="${ATLAS_SPORTS_LIVE_SOURCE_GID:-1000}"' in source

    assert "LiveSourceRegistry" in source
    assert "registry.ensure()" in source

    # Bootstrap must never embed provider/source credentials.
    assert "stream_url" not in source
    assert "username" not in source
    assert "password" not in source


def test_bootstrap_creates_empty_v1_catalog_as_writer(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state/live-sources.json"

    result = _run(path)

    assert result.returncode == 0, result.stderr

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload == {
        "sources": [],
        "version": 1,
    }

    assert path.stat().st_uid == os.geteuid()
    assert path.stat().st_gid == os.getegid()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    lock = path.with_name(path.name + ".lock")

    assert lock.is_file()
    assert lock.stat().st_uid == os.geteuid()
    assert lock.stat().st_gid == os.getegid()
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600


def test_bootstrap_is_idempotent_for_valid_existing_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state/live-sources.json"

    first = _run(path)
    assert first.returncode == 0, first.stderr

    original = path.read_bytes()

    second = _run(path)

    assert second.returncode == 0, second.stderr
    assert path.read_bytes() == original


def test_bootstrap_never_erases_existing_sources(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state/live-sources.json"
    path.parent.mkdir(parents=True)

    payload = {
        "version": 1,
        "sources": [
            {
                "id": "existing",
                "name": "Existing",
                "stream_url": "http://dispatcharr.invalid/proxy/ts/stream/example",
                "standalone": True,
            }
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    path.chmod(0o600)

    result = _run(path)

    assert result.returncode == 0, result.stderr

    after = json.loads(path.read_text(encoding="utf-8"))

    assert after["sources"][0]["id"] == "existing"


def test_bootstrap_rejects_malformed_existing_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state/live-sources.json"
    path.parent.mkdir(parents=True)

    path.write_text(
        '{"version":999,"sources":[]}\n',
        encoding="utf-8",
    )
    path.chmod(0o600)

    before = path.read_bytes()

    result = _run(path)

    assert result.returncode != 0
    assert path.read_bytes() == before


def test_bootstrap_rejects_symlink_state(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"
    target.write_text(
        '{"version":1,"sources":[]}\n',
        encoding="utf-8",
    )

    path = tmp_path / "state/live-sources.json"
    path.parent.mkdir(parents=True)
    path.symlink_to(target)

    result = _run(path)

    assert result.returncode != 0
    assert path.is_symlink()


def test_update_runs_bootstrap_before_maintenance_and_backup() -> None:
    source = UPDATE.read_text(encoding="utf-8")

    command_start = source.index("atlas_command_update()")
    body = source[command_start:]

    bootstrap = body.index(
        "atlas_sports_live_source_bootstrap_provision"
    )
    maintenance = body.index(
        "atlas_command_maintenance enable"
    )
    backup = body.index(
        "atlas_command_backup --notes"
    )
    apply_scope = body.index(
        "atlas_update_apply_scope"
    )

    assert bootstrap < maintenance < backup < apply_scope


def test_core_only_update_does_not_bootstrap_sports_state() -> None:
    source = UPDATE.read_text(encoding="utf-8")

    assert """if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]""" in source
