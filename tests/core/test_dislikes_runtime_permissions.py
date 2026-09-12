"""Runtime permission contracts for API-owned Dislikes persistence."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/lib/dislikes-runtime.sh"
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
    environment["ATLAS_DISLIKES_RUNTIME_UID"] = str(os.geteuid())
    environment["ATLAS_DISLIKES_RUNTIME_GID"] = str(os.getegid())
    environment["ATLAS_DISLIKES_RUNTIME_FILE_GID"] = str(os.getegid())

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


def test_dislikes_runtime_helper_exists() -> None:
    assert HELPER.is_file()


def test_helper_defines_narrow_dislikes_contract() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "ATLAS_DISLIKES_RUNTIME_UID" in source
    assert "ATLAS_DISLIKES_RUNTIME_GID" in source
    assert "ATLAS_DISLIKES_RUNTIME_MODE" in source
    assert "ATLAS_DISLIKES_RUNTIME_FILE_GID" in source
    assert "ATLAS_DISLIKES_RUNTIME_FILE_MODE" in source

    assert "20000" in source
    assert "2770" in source
    assert "0640" in source

    assert "ATLAS_IDENTITY_DIR" in source
    assert "%s/dislikes" in source

    # Dislikes owns only its narrow subtree. Never grant mutation authority
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

    assert "atlas_dislikes_runtime_provision()" in source
    assert "atlas_dislikes_runtime_verify()" in source


def test_ingress_apply_provisions_dislikes_runtime() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    apply_start = source.index("atlas_update_ingress_apply()")
    apply_end = source.find("\n}\n", apply_start)

    assert apply_end != -1

    body = source[apply_start:apply_end]

    assert "dislikes-runtime.sh" in body
    assert "atlas_dislikes_runtime_provision" in body


def test_core_apply_does_not_provision_dislikes_runtime() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    core_start = source.index("atlas_update_core_apply()")
    core_end = source.find("\n}\n", core_start)

    assert core_end != -1

    body = source[core_start:core_end]

    assert "atlas_dislikes_runtime_provision" not in body



def test_ingress_update_bootstraps_dislikes_before_maintenance_and_backup() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    transaction_start = source.index(
        "echo 'Target artifact preflight: PASS'"
    )
    maintenance = source.index(
        "if ! atlas_command_maintenance enable",
        transaction_start,
    )
    backup = source.index(
        "if ! atlas_command_backup --notes",
        maintenance,
    )

    premaintenance = source[transaction_start:maintenance]

    assert 'scripts/lib/dislikes-runtime.sh' in premaintenance
    assert "atlas_dislikes_runtime_provision" in premaintenance

    bootstrap = source.index(
        "atlas_dislikes_runtime_provision",
        transaction_start,
    )

    assert bootstrap < maintenance < backup


def test_provision_creates_exact_runtime_contract(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    result = _run(
        "atlas_dislikes_runtime_provision",
        identity=identity,
    )

    assert result.returncode == 0, result.stderr

    dislikes = identity / "dislikes"

    assert dislikes.is_dir()
    assert dislikes.stat().st_uid == os.geteuid()
    assert dislikes.stat().st_gid == os.getegid()
    assert _mode(dislikes) == 0o2770


def test_provision_is_idempotent(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    first = _run(
        "atlas_dislikes_runtime_provision",
        identity=identity,
    )
    second = _run(
        "atlas_dislikes_runtime_provision",
        identity=identity,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr

    dislikes = identity / "dislikes"

    assert dislikes.stat().st_uid == os.geteuid()
    assert dislikes.stat().st_gid == os.getegid()
    assert _mode(dislikes) == 0o2770


def test_provision_repairs_canonical_paths_without_changing_content(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"
    dislikes = identity / "dislikes"
    records = dislikes / "records"

    records.mkdir(parents=True)

    registry = dislikes / "dislikes.json"
    registry.write_text(
        '{"schema_version":1,"dislikes":{}}\n',
        encoding="utf-8",
    )

    existing = records / ("dis_" + ("a" * 32) + ".json")
    existing.write_text(
        '{"schema_version":1}\n',
        encoding="utf-8",
    )

    os.chmod(dislikes, 0o700)
    os.chmod(records, 0o700)
    os.chmod(registry, 0o600)
    os.chmod(existing, 0o600)

    registry_content = registry.read_text(encoding="utf-8")
    record_content = existing.read_text(encoding="utf-8")

    result = _run(
        "atlas_dislikes_runtime_provision",
        identity=identity,
    )

    assert result.returncode == 0, result.stderr

    assert _mode(dislikes) == 0o2770
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
        "atlas_dislikes_runtime_provision",
        identity=identity,
    )
    assert provision.returncode == 0, provision.stderr

    dislikes = identity / "dislikes"
    os.chmod(dislikes, 0o2750)

    verify = _run(
        "atlas_dislikes_runtime_verify",
        identity=identity,
    )

    assert verify.returncode != 0
    assert "mode mismatch" in verify.stderr
    assert str(dislikes) in verify.stderr


def test_provision_rejects_dislikes_path_that_is_file(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"
    identity.mkdir()

    dislikes = identity / "dislikes"
    dislikes.write_text(
        "not a directory\n",
        encoding="utf-8",
    )

    result = _run(
        "atlas_dislikes_runtime_provision",
        identity=identity,
    )

    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_verify_detects_records_directory_drift(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    provision = _run(
        "atlas_dislikes_runtime_provision",
        identity=identity,
    )
    assert provision.returncode == 0, provision.stderr

    records = identity / "dislikes" / "records"
    os.chmod(records, 0o2750)

    verify = _run(
        "atlas_dislikes_runtime_verify",
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
        "atlas_dislikes_runtime_provision",
        identity=identity,
    )
    assert provision.returncode == 0, provision.stderr

    registry = identity / "dislikes" / "dislikes.json"
    registry.write_text(
        '{"schema_version":1,"dislikes":{}}\n',
        encoding="utf-8",
    )
    os.chmod(registry, 0o600)

    verify = _run(
        "atlas_dislikes_runtime_verify",
        identity=identity,
    )

    assert verify.returncode != 0
    assert "not group-readable" in verify.stderr


def test_ingress_verifier_checks_dislikes_runtime() -> None:
    source = VERIFY_INGRESS.read_text(encoding="utf-8")

    assert "dislikes-runtime.sh" in source
    assert "atlas_dislikes_runtime_verify" in source
    assert "Atlas API Dislikes persistence access" in source
