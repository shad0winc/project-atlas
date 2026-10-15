"""Runtime permission contract for API-owned Request persistence."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/lib/requests-runtime.sh"
UPDATE_SCRIPT = ROOT / "scripts/commands/update.sh"
VERIFY_INGRESS = ROOT / "scripts/verify-ingress.sh"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _run(
    command: str,
    *,
    runtime_root: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ATLAS_RUNTIME_CONFIG_DIR"] = str(runtime_root)
    environment["ATLAS_REQUESTS_RUNTIME_UID"] = str(os.geteuid())
    environment["ATLAS_REQUESTS_RUNTIME_GID"] = str(os.getegid())
    environment["ATLAS_REQUESTS_RUNTIME_API_UID"] = str(os.geteuid())
    environment["ATLAS_REQUESTS_RUNTIME_FILE_GID"] = str(os.getegid())

    return subprocess.run(
        [
            "bash",
            "-c",
            f'set -euo pipefail; source "{HELPER}"; {command}',
        ],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_requests_runtime_helper_exists() -> None:
    assert HELPER.is_file()


def test_helper_defines_narrow_requests_contract() -> None:
    source = HELPER.read_text(encoding="utf-8")

    assert "ATLAS_REQUESTS_RUNTIME_UID" in source
    assert "ATLAS_REQUESTS_RUNTIME_GID" in source
    assert "ATLAS_REQUESTS_RUNTIME_MODE" in source
    assert "ATLAS_REQUESTS_RUNTIME_API_UID" in source
    assert 'ATLAS_REQUESTS_RUNTIME_API_UID="${ATLAS_REQUESTS_RUNTIME_API_UID:-}"' in source
    assert "docker exec atlas-api id -u" in source
    assert ":-999" not in source
    assert "ATLAS_REQUESTS_RUNTIME_FILE_GID" in source
    assert "ATLAS_REQUESTS_RUNTIME_FILE_MODE" in source
    assert "20000" in source
    assert "2770" in source
    assert "0640" in source
    assert "ATLAS_RUNTIME_CONFIG_DIR" in source
    assert "runtime/requests" in source

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

    assert "atlas_requests_runtime_provision()" in source
    assert "atlas_requests_runtime_verify()" in source


def test_ingress_apply_provisions_requests_runtime() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    start = source.index("atlas_update_ingress_apply()")
    end = source.find("\n}\n", start)
    assert end != -1

    body = source[start:end]
    assert "requests-runtime.sh" in body
    assert "atlas_requests_runtime_provision" in body


def test_core_apply_does_not_provision_requests_runtime() -> None:
    source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    start = source.index("atlas_update_core_apply()")
    end = source.find("\n}\n", start)
    assert end != -1

    body = source[start:end]
    assert "atlas_requests_runtime_provision" not in body


def test_provision_creates_exact_directory_contract(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "atlas"

    result = _run(
        "atlas_requests_runtime_provision",
        runtime_root=runtime_root,
    )

    assert result.returncode == 0, result.stderr

    requests = runtime_root / "runtime" / "requests"

    assert requests.is_dir()
    assert requests.stat().st_uid == os.geteuid()
    assert requests.stat().st_gid == os.getegid()
    assert _mode(requests) == 0o2770


def test_provision_repairs_existing_registry_without_changing_bytes(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "atlas"
    requests = runtime_root / "runtime" / "requests"
    requests.mkdir(parents=True)

    registry = requests / "requests.json"
    payload = (
        b'{"requests":{},"schema_version":2,'
        b'"submission_outbox":{},"submissions":{}}\n'
    )
    registry.write_bytes(payload)
    registry.chmod(0o644)

    result = _run(
        "atlas_requests_runtime_provision",
        runtime_root=runtime_root,
    )

    assert result.returncode == 0, result.stderr
    assert registry.read_bytes() == payload
    assert registry.stat().st_uid == os.geteuid()
    assert registry.stat().st_gid == os.getegid()
    assert _mode(registry) == 0o640


def test_provision_repairs_lock_without_changing_bytes(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "atlas"
    requests = runtime_root / "runtime" / "requests"
    requests.mkdir(parents=True)

    lock = requests / "requests.lock"
    lock.write_bytes(b"")
    lock.chmod(0o644)

    result = _run(
        "atlas_requests_runtime_provision",
        runtime_root=runtime_root,
    )

    assert result.returncode == 0, result.stderr
    assert lock.read_bytes() == b""
    assert lock.stat().st_uid == os.geteuid()
    assert lock.stat().st_gid == os.getegid()
    assert _mode(lock) == 0o640


def test_provision_does_not_mutate_acquisition_routing_file(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "atlas"
    requests = runtime_root / "runtime" / "requests"
    requests.mkdir(parents=True)

    routing = requests / "acquisition-routing.json"
    routing.write_bytes(b'{"reviewed":true}\n')
    routing.chmod(0o600)

    before = (
        routing.read_bytes(),
        routing.stat().st_uid,
        routing.stat().st_gid,
        _mode(routing),
    )

    result = _run(
        "atlas_requests_runtime_provision",
        runtime_root=runtime_root,
    )

    assert result.returncode == 0, result.stderr

    after = (
        routing.read_bytes(),
        routing.stat().st_uid,
        routing.stat().st_gid,
        _mode(routing),
    )

    assert after == before


def test_ingress_verifier_checks_requests_runtime() -> None:
    source = VERIFY_INGRESS.read_text(encoding="utf-8")

    assert "requests-runtime.sh" in source
    assert "atlas_requests_runtime_verify" in source
    assert "Request runtime ownership / access contract" in source
    assert "Atlas API Request persistence access" in source
