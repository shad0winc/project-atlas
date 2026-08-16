"""Source contracts for the isolated API security-audit boundary."""

from pathlib import Path
import os
import shutil
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGRESS = PROJECT_ROOT / "stack" / "ingress.yml"
DEPENDENCIES = PROJECT_ROOT / "apps" / "api" / "atlas_api" / "dependencies.py"


def test_api_receives_only_exact_runtime_event_journal() -> None:
    content = INGRESS.read_text(encoding="utf-8")

    assert (
        "/mnt/storage/configs/atlas/runtime/events.jsonl:"
        "/mnt/storage/configs/atlas/runtime/events.jsonl:rw"
    ) in content
    assert (
        "/mnt/storage/configs/atlas/runtime:"
        "/mnt/storage/configs/atlas/runtime"
    ) not in content
    assert "/mnt/storage/configs/atlas/runtime/subscribers" not in content


def test_api_has_dedicated_event_writer_supplemental_group() -> None:
    content = INGRESS.read_text(encoding="utf-8")

    assert '      - "20000"' in content
    assert '      - "20001"' in content


def test_api_security_audit_path_is_explicit() -> None:
    content = INGRESS.read_text(encoding="utf-8")

    assert (
        'ATLAS_SECURITY_AUDIT_PATH: '
        '"/mnt/storage/configs/atlas/runtime/events.jsonl"'
    ) in content


def test_security_audit_writer_is_composed_as_process_dependency() -> None:
    content = DEPENDENCIES.read_text(encoding="utf-8")

    assert "def get_security_audit_writer():" in content
    assert "SecurityAuditWriter.from_environment()" in content
    assert "audit_publisher=get_security_audit_writer().publish" in content


def test_authorization_dependencies_receive_security_audit_writer() -> None:
    path = (
        PROJECT_ROOT
        / "apps"
        / "api"
        / "atlas_api"
        / "security"
        / "dependencies.py"
    )
    content = path.read_text(encoding="utf-8")

    assert "get_security_audit_writer" in content
    assert "audit_writer=Depends(get_security_audit_writer)" in content
    assert '"security.authorization.denied"' in content


def test_authentication_dependency_audits_pre_service_rejections() -> None:
    content = DEPENDENCIES.read_text(encoding="utf-8")

    assert '"security.authentication.access_rejected"' in content
    assert '"security.session.credential_rejected"' in content
    assert "reason=\"invalid_or_expired\"" in content
    assert "audit_writer=Depends(get_security_audit_writer)" in content


def test_security_state_caches_are_cleared_together() -> None:
    content = DEPENDENCIES.read_text(encoding="utf-8")

    assert "get_refresh_session_registry.cache_clear()" in content
    assert "get_login_attempt_limiter.cache_clear()" in content
    assert "get_security_audit_writer.cache_clear()" in content


AUDIT_RUNTIME = PROJECT_ROOT / "scripts" / "lib" / "audit-runtime.sh"
UPDATE = PROJECT_ROOT / "scripts" / "commands" / "update.sh"
VERIFY_INGRESS = PROJECT_ROOT / "scripts" / "verify-ingress.sh"


def test_audit_runtime_provisions_exact_writer_group_contract() -> None:
    content = AUDIT_RUNTIME.read_text(encoding="utf-8")

    assert "ATLAS_AUDIT_JOURNAL_UID='0'" in content
    assert "ATLAS_AUDIT_JOURNAL_GID='20000'" in content
    assert "ATLAS_AUDIT_JOURNAL_MODE='660'" in content

    assert "atlas_audit_runtime_provision()" in content
    assert "atlas_audit_runtime_verify()" in content

    assert 'chown \\' in content
    assert '"$ATLAS_AUDIT_JOURNAL_UID:$ATLAS_AUDIT_JOURNAL_GID"' in content
    assert 'chmod \\' in content
    assert '"$ATLAS_AUDIT_JOURNAL_MODE"' in content


def test_audit_runtime_rejects_symlinks_and_non_regular_journal() -> None:
    content = AUDIT_RUNTIME.read_text(encoding="utf-8")

    assert '[[ -L "$runtime_dir" ]]' in content
    assert '[[ -e "$runtime_dir" && ! -d "$runtime_dir" ]]' in content
    assert '[[ -L "$journal" ]]' in content
    assert '[[ -e "$journal" && ! -f "$journal" ]]' in content


def test_audit_runtime_does_not_recursively_change_runtime_tree() -> None:
    content = AUDIT_RUNTIME.read_text(encoding="utf-8")

    assert "chown -R" not in content
    assert "chmod -R" not in content


def test_ingress_update_provisions_audit_journal_before_compose_apply() -> None:
    content = UPDATE.read_text(encoding="utf-8")

    function_start = content.index("atlas_update_ingress_apply()")
    function_end = content.index(
        "atlas_update_apply_scope()",
        function_start,
    )
    section = content[function_start:function_end]

    provision = section.index("atlas_audit_runtime_provision")
    compose = section.index("docker compose")

    assert provision < compose
    assert 'source "$ATLAS_PROJECT_DIR/scripts/lib/audit-runtime.sh"' in section


def test_ingress_verification_enforces_audit_runtime_contract() -> None:
    content = VERIFY_INGRESS.read_text(encoding="utf-8")

    assert 'source "$PROJECT_DIR/scripts/lib/audit-runtime.sh"' in content
    assert "atlas_audit_runtime_verify" in content
    assert "Security audit journal ownership / mode contract" in content
    assert "Atlas API can write security audit journal" in content
    assert (
        "test -w /mnt/storage/configs/atlas/runtime/events.jsonl"
        in content
    )



def _require_acl_tools() -> None:
    if shutil.which("getfacl") is None or shutil.which("setfacl") is None:
        import pytest

        pytest.skip("POSIX ACL tools are unavailable")


def _run_audit_runtime(
    command: str,
    *,
    runtime: Path,
    journal: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_AUDIT_RUNTIME_DIR": str(runtime),
            "ATLAS_AUDIT_JOURNAL": str(journal),
        }
    )

    return subprocess.run(
        [
            "bash",
            "-c",
            (
                "set -euo pipefail; "
                f"source {str(AUDIT_RUNTIME)!r}; "
                f"{command}"
            ),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_audit_runtime_normalizes_stale_extended_acl(
    tmp_path: Path,
) -> None:
    _require_acl_tools()

    runtime = tmp_path / "runtime"
    runtime.mkdir()

    journal = runtime / "events.jsonl"
    journal.write_text('{"event":"preserved"}\n', encoding="utf-8")

    before_inode = journal.stat().st_ino
    before_content = journal.read_bytes()

    subprocess.run(
        [
            "setfacl",
            "-m",
            "u:1000:r--,g::---,m::r--",
            str(journal),
        ],
        check=True,
    )

    stale_acl = subprocess.run(
        ["getfacl", "-cp", str(journal)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "user:1000:r--" in stale_acl
    assert "group::---" in stale_acl
    assert "mask::r--" in stale_acl

    result = _run_audit_runtime(
        "atlas_audit_runtime_normalize_acl",
        runtime=runtime,
        journal=journal,
    )

    assert result.returncode == 0, result.stderr

    acl = subprocess.run(
        ["getfacl", "-cp", str(journal)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "user:1000:" not in acl
    assert "mask::" not in acl
    assert journal.stat().st_ino == before_inode
    assert journal.read_bytes() == before_content


def test_audit_runtime_acl_normalization_is_idempotent(
    tmp_path: Path,
) -> None:
    _require_acl_tools()

    runtime = tmp_path / "runtime"
    runtime.mkdir()

    journal = runtime / "events.jsonl"
    journal.write_text("event\n", encoding="utf-8")

    first = _run_audit_runtime(
        "atlas_audit_runtime_normalize_acl",
        runtime=runtime,
        journal=journal,
    )
    second = _run_audit_runtime(
        "atlas_audit_runtime_normalize_acl",
        runtime=runtime,
        journal=journal,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr


def test_audit_runtime_verify_acl_rejects_extended_acl(
    tmp_path: Path,
) -> None:
    _require_acl_tools()

    runtime = tmp_path / "runtime"
    runtime.mkdir()

    journal = runtime / "events.jsonl"
    journal.write_text("event\n", encoding="utf-8")
    journal.chmod(0o660)

    subprocess.run(
        ["setfacl", "-m", "u:1000:r--", str(journal)],
        check=True,
    )

    result = _run_audit_runtime(
        "atlas_audit_runtime_verify_acl",
        runtime=runtime,
        journal=journal,
    )

    assert result.returncode != 0
    assert "unexpected ACL" in result.stderr


def test_audit_runtime_source_requires_acl_normalization() -> None:
    content = AUDIT_RUNTIME.read_text(encoding="utf-8")

    assert "atlas_audit_runtime_require_acl_tools()" in content
    assert "atlas_audit_runtime_normalize_acl()" in content
    assert "atlas_audit_runtime_verify_acl()" in content

    assert 'setfacl -b -- "$journal"' in content
    assert 'getfacl -cp -- "$journal"' in content

    provision_start = content.index("atlas_audit_runtime_provision()")
    verify_start = content.index(
        "atlas_audit_runtime_verify()",
        provision_start,
    )
    provision = content[provision_start:verify_start]

    normalize = provision.index("atlas_audit_runtime_normalize_acl")
    chown = provision.index("chown")
    chmod = provision.index("chmod")

    assert normalize < chown < chmod


def test_audit_runtime_verify_enforces_minimal_acl() -> None:
    content = AUDIT_RUNTIME.read_text(encoding="utf-8")

    verify_start = content.index("atlas_audit_runtime_verify()")
    verify = content[verify_start:]

    assert "atlas_audit_runtime_verify_acl" in verify
    assert "'user::rw-'" in content
    assert "'group::rw-'" in content
    assert "'other::---'" in content
