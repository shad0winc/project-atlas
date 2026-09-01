"""Runtime permission contracts for API-owned Favorites persistence."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/lib/favorites-runtime.sh"
UPDATE_SCRIPT = ROOT / "scripts/commands/update.sh"
VERIFY_INGRESS = ROOT / "scripts/verify-ingress.sh"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _run(
    command: str,
    *,
    identity: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ATLAS_IDENTITY_DIR"] = str(identity)

    # Exercise production behavior without requiring CAP_CHOWN in CI.
    environment["ATLAS_FAVORITES_RUNTIME_UID"] = str(os.geteuid())
    environment["ATLAS_FAVORITES_RUNTIME_GID"] = str(os.getegid())
    environment["ATLAS_FAVORITES_RUNTIME_FILE_GID"] = str(os.getegid())

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


def test_favorites_runtime_helper_exists() -> None:
    assert HELPER.is_file()


def test_helper_defines_narrow_favorites_contract() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "ATLAS_FAVORITES_RUNTIME_UID" in source
    assert "ATLAS_FAVORITES_RUNTIME_GID" in source
    assert "ATLAS_FAVORITES_RUNTIME_MODE" in source
    assert "ATLAS_FAVORITES_RUNTIME_FILE_GID" in source
    assert "ATLAS_FAVORITES_RUNTIME_FILE_MODE" in source

    assert "20000" in source
    assert "2770" in source
    assert "0640" in source

    assert "ATLAS_IDENTITY_DIR" in source
    assert "%s/favorites" in source

    # Favorites owns only its narrow subtree. Never grant mutation authority
    # over the entire Atlas identity root.
    assert '"/mnt/storage/configs/atlas/identity:rw"' not in source


def test_helper_never_uses_recursive_permission_mutation() -> None:
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

    assert "atlas_favorites_runtime_provision()" in source
    assert "atlas_favorites_runtime_verify()" in source


def test_ingress_apply_provisions_favorites_runtime() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    apply_start = source.index("atlas_update_ingress_apply()")
    apply_end = source.find("\n}\n", apply_start)

    assert apply_end != -1

    body = source[apply_start:apply_end]

    assert "favorites-runtime.sh" in body
    assert "atlas_favorites_runtime_provision" in body


def test_core_apply_does_not_provision_favorites_runtime() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    core_start = source.index("atlas_update_core_apply()")
    core_end = source.find("\n}\n", core_start)

    assert core_end != -1

    body = source[core_start:core_end]

    assert "atlas_favorites_runtime_provision" not in body


def test_provision_creates_exact_runtime_contract(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    result = _run(
        "atlas_favorites_runtime_provision",
        identity=identity,
    )

    assert result.returncode == 0, result.stderr

    favorites = identity / "favorites"

    assert favorites.is_dir()
    assert favorites.stat().st_uid == os.geteuid()
    assert favorites.stat().st_gid == os.getegid()
    assert _mode(favorites) == 0o2770


def test_provision_is_idempotent(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    first = _run(
        "atlas_favorites_runtime_provision",
        identity=identity,
    )
    second = _run(
        "atlas_favorites_runtime_provision",
        identity=identity,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr

    favorites = identity / "favorites"

    assert favorites.stat().st_uid == os.geteuid()
    assert favorites.stat().st_gid == os.getegid()
    assert _mode(favorites) == 0o2770


def test_provision_repairs_canonical_paths_without_changing_content(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"
    favorites = identity / "favorites"
    records = favorites / "records"

    records.mkdir(parents=True)

    registry = favorites / "favorites.json"
    registry.write_text(
        '{"schema_version":1,"favorites":{}}\n',
        encoding="utf-8",
    )

    existing = records / ("fav_" + ("a" * 32) + ".json")
    existing.write_text(
        '{"schema_version":1}\n',
        encoding="utf-8",
    )

    os.chmod(favorites, 0o700)
    os.chmod(records, 0o700)
    os.chmod(registry, 0o600)
    os.chmod(existing, 0o600)

    registry_content = registry.read_text(encoding="utf-8")
    record_content = existing.read_text(encoding="utf-8")

    result = _run(
        "atlas_favorites_runtime_provision",
        identity=identity,
    )

    assert result.returncode == 0, result.stderr

    assert _mode(favorites) == 0o2770
    assert _mode(records) == 0o2770

    assert registry.stat().st_gid == os.getegid()
    assert existing.stat().st_gid == os.getegid()

    assert _mode(registry) == 0o640
    assert _mode(existing) == 0o640

    assert registry.read_text(encoding="utf-8") == registry_content
    assert existing.read_text(encoding="utf-8") == record_content


def test_verify_detects_mode_drift(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    provision = _run(
        "atlas_favorites_runtime_provision",
        identity=identity,
    )
    assert provision.returncode == 0, provision.stderr

    favorites = identity / "favorites"
    os.chmod(favorites, 0o2750)

    verify = _run(
        "atlas_favorites_runtime_verify",
        identity=identity,
    )

    assert verify.returncode != 0
    assert "mode mismatch" in verify.stderr
    assert str(favorites) in verify.stderr


def test_provision_rejects_favorites_path_that_is_file(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"
    identity.mkdir()

    favorites = identity / "favorites"
    favorites.write_text(
        "not a directory\n",
        encoding="utf-8",
    )

    result = _run(
        "atlas_favorites_runtime_provision",
        identity=identity,
    )

    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_verify_detects_records_directory_drift(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    provision = _run(
        "atlas_favorites_runtime_provision",
        identity=identity,
    )
    assert provision.returncode == 0, provision.stderr

    records = identity / "favorites" / "records"
    os.chmod(records, 0o2750)

    verify = _run(
        "atlas_favorites_runtime_verify",
        identity=identity,
    )

    assert verify.returncode != 0
    assert "mode mismatch" in verify.stderr
    assert str(records) in verify.stderr


def test_verify_detects_unreadable_registry(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    provision = _run(
        "atlas_favorites_runtime_provision",
        identity=identity,
    )
    assert provision.returncode == 0, provision.stderr

    registry = identity / "favorites" / "favorites.json"
    registry.write_text(
        '{"schema_version":1,"favorites":{}}\n',
        encoding="utf-8",
    )
    os.chmod(registry, 0o600)

    verify = _run(
        "atlas_favorites_runtime_verify",
        identity=identity,
    )

    assert verify.returncode != 0
    assert "not group-readable" in verify.stderr


def test_ingress_verifier_checks_favorites_runtime() -> None:
    source = VERIFY_INGRESS.read_text(encoding="utf-8")

    assert "favorites-runtime.sh" in source
    assert "atlas_favorites_runtime_verify" in source
    assert "Atlas API Favorites persistence access" in source
