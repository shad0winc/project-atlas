"""Source contracts for the isolated API security-audit boundary."""

from pathlib import Path


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
