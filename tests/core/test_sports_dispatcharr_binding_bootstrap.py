from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/lib/sports-dispatcharr-binding-bootstrap.sh"
UPDATE = ROOT / "scripts/commands/update.sh"
UPDATE_TEST = ROOT / "tests/core/test_update_transaction.py"

EMPTY_DOCUMENT = {
    "version": 1,
    "bindings": {},
}


def run_helper(
    path: Path,
    *,
    uid: int | None = None,
    gid: int | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ATLAS_SPORTS_DISPATCHARR_BINDINGS_PATH"] = str(path)

    if uid is not None:
        environment["ATLAS_SPORTS_DISPATCHARR_BINDINGS_UID"] = str(uid)

    if gid is not None:
        environment["ATLAS_SPORTS_DISPATCHARR_BINDINGS_GID"] = str(gid)

    return subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$1"; '
                "atlas_sports_dispatcharr_binding_bootstrap_provision"
            ),
            "atlas-bootstrap-test",
            str(HELPER),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_bootstrap_helper_exists_and_exposes_canonical_provisioner() -> None:
    assert HELPER.is_file()

    source = HELPER.read_text(encoding="utf-8")

    assert "atlas_sports_dispatcharr_binding_bootstrap_provision() {" in source
    assert (
        "/mnt/storage/configs/sportyfin/state/"
        "dispatcharr-channel-bindings.json"
        in source
    )


def test_missing_registry_materializes_canonical_empty_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state/dispatcharr-channel-bindings.json"

    result = run_helper(
        path,
        uid=os.getuid(),
        gid=os.getgid(),
    )

    assert result.returncode == 0, result.stderr
    assert path.is_file()
    assert not path.is_symlink()

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload == EMPTY_DOCUMENT
    assert (
        "SPORTS_DISPATCHARR_BINDING_BOOTSTRAP_STATE=PASS"
        in result.stdout
    )


def test_existing_valid_registry_is_preserved(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state/dispatcharr-channel-bindings.json"
    path.parent.mkdir(parents=True)

    original = (
        '{"version":1,"bindings":'
        '{"atlas:test":{'
        '"dispatcharr_channel_id":42,'
        '"dispatcharr_channel_uuid":"channel-uuid-test"'
        '}}}\n'
    )

    path.write_text(original, encoding="utf-8")
    path.chmod(0o600)

    result = run_helper(
        path,
        uid=os.getuid(),
        gid=os.getgid(),
    )

    assert result.returncode == 0, result.stderr
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    "payload",
    [
        "{}\n",
        '{"version":2,"bindings":{}}\n',
        '{"version":1,"bindings":[]}\n',
        "not-json\n",
    ],
)
def test_existing_invalid_registry_fails_closed_without_rewrite(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "state/dispatcharr-channel-bindings.json"
    path.parent.mkdir(parents=True)
    path.write_text(payload, encoding="utf-8")

    result = run_helper(
        path,
        uid=os.getuid(),
        gid=os.getgid(),
    )

    assert result.returncode != 0
    assert path.read_text(encoding="utf-8") == payload


def test_symbolic_registry_path_fails_closed(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real.json"
    real.write_text(
        '{"version":1,"bindings":{}}\n',
        encoding="utf-8",
    )

    path = tmp_path / "state/dispatcharr-channel-bindings.json"
    path.parent.mkdir(parents=True)
    path.symlink_to(real)

    result = run_helper(
        path,
        uid=os.getuid(),
        gid=os.getgid(),
    )

    assert result.returncode != 0
    assert path.is_symlink()
    assert json.loads(real.read_text(encoding="utf-8")) == EMPTY_DOCUMENT


def test_bootstrap_requires_absolute_path(
    tmp_path: Path,
) -> None:
    environment = os.environ.copy()
    environment["ATLAS_SPORTS_DISPATCHARR_BINDINGS_PATH"] = (
        "relative/dispatcharr-channel-bindings.json"
    )
    environment["ATLAS_SPORTS_DISPATCHARR_BINDINGS_UID"] = str(os.getuid())
    environment["ATLAS_SPORTS_DISPATCHARR_BINDINGS_GID"] = str(os.getgid())

    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$1"; '
                "atlas_sports_dispatcharr_binding_bootstrap_provision"
            ),
            "atlas-bootstrap-test",
            str(HELPER),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0


def test_bootstrap_contract_has_explicit_ownership_and_mode_checks() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "UID" in source
    assert "GID" in source
    assert "mode" in source.lower()
    assert "symbolic" in source.lower()


def test_update_sources_binding_bootstrap_for_ingress() -> None:
    source = UPDATE.read_text(encoding="utf-8")

    assert (
        'source "$ATLAS_PROJECT_DIR/scripts/lib/'
        'sports-dispatcharr-binding-bootstrap.sh"'
        in source
    )

    assert "atlas_sports_dispatcharr_binding_bootstrap_provision" in source


def test_binding_bootstrap_precedes_maintenance_and_backup_statically() -> None:
    source = UPDATE.read_text(encoding="utf-8")

    bootstrap = source.index(
        "atlas_sports_dispatcharr_binding_bootstrap_provision"
    )
    maintenance = source.index(
        "atlas_command_maintenance enable",
        bootstrap,
    )
    backup = source.index(
        "atlas_command_backup --notes",
        maintenance,
    )

    assert bootstrap < maintenance < backup


def test_binding_bootstrap_failure_aborts_before_maintenance_contract() -> None:
    source = UPDATE_TEST.read_text(encoding="utf-8")

    assert "ATLAS_TEST_SPORTS_DISPATCHARR_BINDING_BOOTSTRAP_STATUS" in source
    assert "sports-dispatcharr-binding-bootstrap:provision" in source
    assert (
        "Sports Dispatcharr binding bootstrap failed before maintenance"
        in source
    )


def test_core_update_does_not_bootstrap_dispatcharr_binding_state_contract() -> None:
    source = UPDATE_TEST.read_text(encoding="utf-8")

    assert (
        "test_core_update_does_not_run_sports_dispatcharr_binding_bootstrap"
        in source
    )
