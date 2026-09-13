from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts" / "commands" / "deployment.sh"
HELP = PROJECT_ROOT / "scripts" / "commands" / "help.sh"

COMMAND = "recover-failed-rollback"
FUNCTION = "atlas_deployment_recover_failed_rollback"


def recovery_section() -> str:
    content = DEPLOYMENT.read_text(encoding="utf-8")
    marker = f"{FUNCTION}() {{"
    assert marker in content, (
        "post-rollback finalization function is not implemented yet: "
        f"{FUNCTION}"
    )

    start = content.index(marker)
    tail = content[start + len(marker):]

    import re

    next_function = re.search(
        r"\n[a-zA-Z_][a-zA-Z0-9_]*\(\)[ \t]*\{",
        tail,
    )

    assert next_function is not None, (
        "post-rollback finalization function has no following "
        "shell-function boundary"
    )

    end = start + len(marker) + next_function.start() + 1
    return content[start:end]


def test_deployment_cli_exposes_failed_rollback_recovery() -> None:
    deployment = DEPLOYMENT.read_text(encoding="utf-8")
    help_text = HELP.read_text(encoding="utf-8")

    usage = f"atlas deployment {COMMAND} <deployment-id>"

    assert usage in deployment
    assert usage in help_text
    assert f"{COMMAND})" in deployment
    assert f"{FUNCTION} " in deployment


def test_recovery_requires_original_transaction_to_remain_failed() -> None:
    section = recovery_section()

    assert "status" in section
    assert "failed" in section

    forbidden = (
        'atlas_deployment_set_status "$transaction" rolled_back',
        'atlas_deployment_set_status "$transaction" verified',
        'atlas_deployment_set_status "$transaction" recovered_pre_apply',
    )

    for phrase in forbidden:
        assert phrase not in section


def test_recovery_requires_existing_failed_transaction_lock_owner() -> None:
    section = recovery_section()

    assert "atlas_deployment_lock_matches" in section
    assert "another deployment owns the active lock" in section

    # This recovery resumes an already-held failed deployment transaction.
    # It must not create a replacement lock identity.
    assert "atlas_deployment_acquire_lock" not in section


def test_recovery_requires_maintenance_already_enabled() -> None:
    section = recovery_section()

    assert "atlas_maintenance_flag" in section
    assert "maintenance" in section.lower()

    # Recovery starts from the deliberately held state. It must not silently
    # manufacture that state as part of eligibility.
    before_first_verify = section.split(
        "atlas_deployment_verify_rollback_runtime", 1
    )[0]
    assert "atlas_command_maintenance enable" not in before_first_verify


def test_recovery_requires_previous_verified_baseline_still_current() -> None:
    section = recovery_section()

    assert "previous_baseline" in section
    assert "atlas_deployment_current_id" in section
    assert "verified" in section


def test_recovery_requires_existing_historical_rollback_source() -> None:
    section = recovery_section()

    assert "atlas_deployment_rollback_recovery_source" in section


def test_recovery_uses_rollback_aware_verification_before_and_after_reopen() -> None:
    section = recovery_section()

    assert section.count("atlas_deployment_verify_rollback_runtime") >= 2

    first_verify = section.index("atlas_deployment_verify_rollback_runtime")
    disable = section.index("atlas_command_maintenance disable")
    second_verify = section.index(
        "atlas_deployment_verify_rollback_runtime",
        first_verify + 1,
    )

    assert first_verify < disable < second_verify


def test_recovery_reenables_maintenance_if_public_verification_fails() -> None:
    section = recovery_section()

    first_verify = section.index("atlas_deployment_verify_rollback_runtime")
    disable = section.index(
        "atlas_command_maintenance disable",
        first_verify,
    )
    second_verify = section.index(
        "atlas_deployment_verify_rollback_runtime",
        disable,
    )

    tail = section[second_verify:]

    assert "atlas_command_maintenance enable" in tail


def test_recovery_does_not_repeat_runtime_restore_or_apply() -> None:
    section = recovery_section()

    forbidden = (
        "atlas_deployment_restore_surface",
        "atlas_update_apply_scope",
        "docker compose",
        "docker restart",
        "docker pull",
        "docker build",
        "docker image tag",
    )

    for phrase in forbidden:
        assert phrase not in section


def test_recovery_publishes_separate_verified_reconciliation_baseline() -> None:
    section = recovery_section()

    # The failed transaction itself is immutable evidence. Successful recovery
    # therefore needs an independently named baseline record.
    assert "reconciliation" in section.lower()
    assert "atlas_deployment_set_current" in section
    assert "verified" in section

    # The failed deployment must never become the current baseline.
    assert 'atlas_deployment_set_current "$identifier"' not in section


def test_recovery_finalizes_before_releasing_original_failed_lock() -> None:
    section = recovery_section()

    set_current = section.index("atlas_deployment_set_current")
    release = section.index(
        'atlas_deployment_release_lock "$identifier"',
        set_current,
    )

    assert set_current < release


def test_recovery_never_relabels_original_failed_transaction() -> None:
    section = recovery_section()

    # Any status write against the original failed transaction would destroy
    # the immutable failure outcome that this recovery path exists to retain.
    assert 'atlas_deployment_set_status "$transaction"' not in section
