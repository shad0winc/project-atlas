from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/lib/identity-writer-runtime.sh"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _run(
    command: str,
    *,
    users: Path,
    identity: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ATLAS_USERS_DIR"] = str(users)
    environment["ATLAS_IDENTITY_DIR"] = str(identity)

    # Exercise the real provisioning path without requiring CAP_CHOWN in CI.
    # Source-contract tests separately pin the production defaults.
    environment["ATLAS_IDENTITY_WRITER_USERS_UID"] = str(os.geteuid())
    environment["ATLAS_IDENTITY_WRITER_USERS_GID"] = str(os.getegid())
    environment["ATLAS_IDENTITY_WRITER_INVITATIONS_UID"] = str(os.geteuid())
    environment["ATLAS_IDENTITY_WRITER_INVITATIONS_GID"] = str(os.getegid())

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


def test_provision_creates_exact_runtime_contract(
    tmp_path: Path,
) -> None:
    users = tmp_path / "users"
    identity = tmp_path / "identity"
    invitations = identity / "invitations"

    result = _run(
        "atlas_identity_writer_runtime_provision",
        users=users,
        identity=identity,
    )

    assert result.returncode == 0, result.stderr

    assert users.is_dir()
    assert invitations.is_dir()

    assert users.stat().st_uid == os.geteuid()
    assert users.stat().st_gid == os.getegid()
    assert _mode(users) == 0o2770

    assert invitations.stat().st_uid == os.geteuid()
    assert invitations.stat().st_gid == os.getegid()
    assert _mode(invitations) == 0o2770


def test_provision_is_idempotent(
    tmp_path: Path,
) -> None:
    users = tmp_path / "users"
    identity = tmp_path / "identity"

    first = _run(
        "atlas_identity_writer_runtime_provision",
        users=users,
        identity=identity,
    )
    second = _run(
        "atlas_identity_writer_runtime_provision",
        users=users,
        identity=identity,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr

    invitations = identity / "invitations"

    assert users.stat().st_uid == os.geteuid()
    assert users.stat().st_gid == os.getegid()
    assert _mode(users) == 0o2770

    assert invitations.stat().st_uid == os.geteuid()
    assert invitations.stat().st_gid == os.getegid()
    assert _mode(invitations) == 0o2770


def test_provision_preserves_existing_children(
    tmp_path: Path,
) -> None:
    users = tmp_path / "users"
    invitations = tmp_path / "identity" / "invitations"

    users.mkdir(parents=True)
    invitations.mkdir(parents=True)

    user_file = users / "users.json"
    invitation_file = invitations / "invitations.json"

    user_file.write_text('{"users":[]}\n', encoding="utf-8")
    invitation_file.write_text(
        '{"invitations":[]}\n',
        encoding="utf-8",
    )

    os.chmod(user_file, 0o640)
    os.chmod(invitation_file, 0o600)

    user_before = (
        user_file.stat().st_uid,
        user_file.stat().st_gid,
        _mode(user_file),
    )
    invitation_before = (
        invitation_file.stat().st_uid,
        invitation_file.stat().st_gid,
        _mode(invitation_file),
    )

    result = _run(
        "atlas_identity_writer_runtime_provision",
        users=users,
        identity=tmp_path / "identity",
    )

    assert result.returncode == 0, result.stderr

    assert (
        user_file.stat().st_uid,
        user_file.stat().st_gid,
        _mode(user_file),
    ) == user_before

    assert (
        invitation_file.stat().st_uid,
        invitation_file.stat().st_gid,
        _mode(invitation_file),
    ) == invitation_before


def test_provision_rejects_users_path_that_is_file(
    tmp_path: Path,
) -> None:
    users = tmp_path / "users"
    users.write_text("not a directory\n", encoding="utf-8")

    result = _run(
        "atlas_identity_writer_runtime_provision",
        users=users,
        identity=tmp_path / "identity",
    )

    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_provision_rejects_invitation_path_that_is_file(
    tmp_path: Path,
) -> None:
    users = tmp_path / "users"
    identity = tmp_path / "identity"

    users.mkdir()
    identity.mkdir()

    invitations = identity / "invitations"
    invitations.write_text(
        "not a directory\n",
        encoding="utf-8",
    )

    result = _run(
        "atlas_identity_writer_runtime_provision",
        users=users,
        identity=identity,
    )

    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_verify_detects_mode_drift(
    tmp_path: Path,
) -> None:
    users = tmp_path / "users"
    identity = tmp_path / "identity"

    provision = _run(
        "atlas_identity_writer_runtime_provision",
        users=users,
        identity=identity,
    )
    assert provision.returncode == 0, provision.stderr

    os.chmod(users, 0o2750)

    verify = _run(
        "atlas_identity_writer_runtime_verify",
        users=users,
        identity=identity,
    )

    assert verify.returncode != 0
    assert "mode mismatch" in verify.stderr


def test_environment_paths_are_honored(
    tmp_path: Path,
) -> None:
    users = tmp_path / "custom-users"
    identity = tmp_path / "custom-identity"

    result = _run(
        '''
printf 'users=%s\n' "$(atlas_identity_writer_runtime_users_dir)"
printf 'invitations=%s\n' "$(atlas_identity_writer_runtime_invitations_dir)"
''',
        users=users,
        identity=identity,
    )

    assert result.returncode == 0, result.stderr
    assert f"users={users}" in result.stdout
    assert f"invitations={identity / 'invitations'}" in result.stdout
