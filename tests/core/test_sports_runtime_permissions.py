"""Runtime permission contracts for shared Sports playback state."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/lib/sports-runtime.sh"
UPDATE_SCRIPT = ROOT / "scripts/commands/update.sh"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _run(
    command: str,
    *,
    runtime_dir: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ATLAS_SPORTS_RUNTIME_DIR"] = str(runtime_dir)

    # Exercise the real helper without requiring CAP_CHOWN in CI.
    environment["ATLAS_SPORTS_RUNTIME_UID"] = str(os.geteuid())
    environment["ATLAS_SPORTS_RUNTIME_GID"] = str(os.getegid())
    environment["ATLAS_SPORTS_RUNTIME_MODE"] = "2770"
    environment["ATLAS_SPORTS_RUNTIME_FILE_GID"] = str(os.getegid())
    environment["ATLAS_SPORTS_RUNTIME_FILE_MODE"] = "0660"

    return subprocess.run(
        [
            "bash",
            "-c",
            f'''
set -euo pipefail
source "{HELPER}"
{command}
''',
        ],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sports_runtime_helper_exists() -> None:
    assert HELPER.is_file()


def test_helper_defines_narrow_sports_runtime_contract() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "ATLAS_SPORTS_RUNTIME_DIR" in source
    assert "ATLAS_SPORTS_RUNTIME_UID" in source
    assert "ATLAS_SPORTS_RUNTIME_GID" in source
    assert "ATLAS_SPORTS_RUNTIME_MODE" in source
    assert "ATLAS_SPORTS_RUNTIME_FILE_GID" in source
    assert "ATLAS_SPORTS_RUNTIME_FILE_MODE" in source

    assert "/mnt/storage/configs/atlas/runtime/sports" in source
    assert "20000" in source
    assert "2770" in source
    assert "0660" in source

    assert "resource-pool.json" in source
    assert "live-sessions.json" not in source


def test_helper_does_not_recursively_change_permissions() -> None:
    source = HELPER.read_text(encoding="utf-8")

    forbidden = (
        "chmod -R",
        "chmod --recursive",
        "chown -R",
        "chown --recursive",
    )

    for token in forbidden:
        assert token not in source


def test_helper_has_provision_and_verify_boundaries() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "atlas_sports_runtime_provision()" in source
    assert "atlas_sports_runtime_verify()" in source
    assert "atlas_sports_runtime_verify_directory()" in source


def test_ingress_apply_provisions_sports_runtime_before_compose() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    apply_start = source.index("atlas_update_ingress_apply()")
    apply_end = source.index(
        "\natlas_update_apply_scope()",
        apply_start,
    )

    body = source[apply_start:apply_end]

    assert 'scripts/lib/sports-runtime.sh' in body
    assert "atlas_sports_runtime_provision" in body

    provision = body.index("atlas_sports_runtime_provision")
    compose = body.index("docker compose")

    assert provision < compose


def test_core_apply_does_not_provision_sports_runtime() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    core_start = source.index("atlas_update_core_apply()")
    core_end = source.index(
        "\natlas_update_ingress_apply()",
        core_start,
    )

    body = source[core_start:core_end]

    assert "sports-runtime.sh" not in body
    assert "atlas_sports_runtime_provision" not in body


def test_provision_creates_exact_directory_contract(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "sports"

    result = _run(
        "atlas_sports_runtime_provision",
        runtime_dir=runtime_dir,
    )

    assert result.returncode == 0, result.stderr
    assert runtime_dir.is_dir()
    assert not runtime_dir.is_symlink()
    assert runtime_dir.stat().st_uid == os.geteuid()
    assert runtime_dir.stat().st_gid == os.getegid()
    assert _mode(runtime_dir) == 0o2770


def test_provision_repairs_directory_mode(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "sports"
    runtime_dir.mkdir()
    runtime_dir.chmod(0o700)

    result = _run(
        "atlas_sports_runtime_provision",
        runtime_dir=runtime_dir,
    )

    assert result.returncode == 0, result.stderr
    assert _mode(runtime_dir) == 0o2770


def test_provision_rejects_file_in_place_of_directory(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "sports"
    runtime_dir.write_text("not-a-directory\n", encoding="utf-8")

    result = _run(
        "atlas_sports_runtime_provision",
        runtime_dir=runtime_dir,
    )

    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_provision_rejects_symlink_runtime_path(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()

    runtime_dir = tmp_path / "sports"
    runtime_dir.symlink_to(target, target_is_directory=True)

    result = _run(
        "atlas_sports_runtime_provision",
        runtime_dir=runtime_dir,
    )

    assert result.returncode != 0
    assert "must not be a symlink" in result.stderr

def test_provision_does_not_create_resource_pool_files(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "sports"

    result = _run(
        "atlas_sports_runtime_provision",
        runtime_dir=runtime_dir,
    )

    assert result.returncode == 0, result.stderr
    assert not (runtime_dir / "resource-pool.json").exists()
    assert not (runtime_dir / "resource-pool.json.lock").exists()


def test_provision_repairs_resource_pool_file_contract(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "sports"
    runtime_dir.mkdir()

    state = runtime_dir / "resource-pool.json"
    lock = runtime_dir / "resource-pool.json.lock"

    state.write_text(
        '{"version":1,"leases":{}}\n',
        encoding="utf-8",
    )
    lock.touch()

    state.chmod(0o600)
    lock.chmod(0o600)

    original_state = state.read_text(
        encoding="utf-8",
    )

    result = _run(
        "atlas_sports_runtime_provision",
        runtime_dir=runtime_dir,
    )

    assert result.returncode == 0, result.stderr
    assert state.read_text(encoding="utf-8") == original_state
    assert state.stat().st_uid == os.geteuid()
    assert lock.stat().st_uid == os.geteuid()
    assert state.stat().st_gid == os.getegid()
    assert lock.stat().st_gid == os.getegid()
    assert _mode(state) == 0o660
    assert _mode(lock) == 0o660


def test_verify_rejects_private_resource_pool_file_mode(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "sports"

    provision = _run(
        "atlas_sports_runtime_provision",
        runtime_dir=runtime_dir,
    )

    assert provision.returncode == 0, provision.stderr

    state = runtime_dir / "resource-pool.json"
    state.write_text(
        '{"version":1,"leases":{}}\n',
        encoding="utf-8",
    )
    state.chmod(0o600)

    result = _run(
        "atlas_sports_runtime_verify",
        runtime_dir=runtime_dir,
    )

    assert result.returncode != 0
    assert "file mode mismatch" in result.stderr


def test_provision_rejects_resource_pool_symlink(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "sports"
    runtime_dir.mkdir()

    target = tmp_path / "target.json"
    target.write_text(
        '{"version":1,"leases":{}}\n',
        encoding="utf-8",
    )

    state = runtime_dir / "resource-pool.json"
    state.symlink_to(target)

    result = _run(
        "atlas_sports_runtime_provision",
        runtime_dir=runtime_dir,
    )

    assert result.returncode != 0
    assert "must not be a symlink" in result.stderr
