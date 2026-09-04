from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HELPER = (
    ROOT
    / "scripts"
    / "lib"
    / "sports-backend-recovery.sh"
)

DOC = (
    ROOT
    / "docs"
    / "architecture"
    / "BACKUP_RECOVERY.md"
)


def test_backend_recovery_uses_native_consistent_database_capture() -> None:
    text = HELPER.read_text(
        encoding="utf-8"
    )

    assert "_dump_postgresql" in text
    assert "src.backup(dst)" in text

    assert "PGDMP" in text
    assert "PRAGMA integrity_check" in text

    assert "teamarr.db-wal" not in text
    assert "teamarr.db-shm" not in text

    assert 'cp -a -- "$dispatch_root/db"' not in text


def test_backend_recovery_declares_exact_native_artifacts() -> None:
    text = HELPER.read_text(
        encoding="utf-8"
    )

    assert (
        "backend-recovery/dispatcharr/database.dump"
        in text
    )

    assert (
        "backend-recovery/dispatcharr/jwt"
        in text
    )

    assert (
        "backend-recovery/teamarr/teamarr.db"
        in text
    )


def test_backend_recovery_docs_preserve_twelve_surface_boundary() -> None:
    text = DOC.read_text(
        encoding="utf-8"
    )

    assert (
        "canonical twelve filesystem replacement surfaces"
        in text
    )

    assert (
        "Recovery format 1 remains"
        in text
    )

    assert (
        "Live application must fail closed"
        in text
    )


def test_backup_command_emits_recovery_format_two() -> None:
    backup = (
        ROOT
        / "scripts"
        / "commands"
        / "backup.sh"
    ).read_text(
        encoding="utf-8"
    )

    assert "Recovery format: 2" in backup

    assert (
        """printf '%s\\n' '2' > "$recovery_format\""""
        in backup
    )

    assert (
        'atlas_sports_backend_recovery_capture '
        '"$snapshot_root"'
        in backup
    )

    assert (
        '''-C "$snapshot_root" \\
    state \\
    backend-recovery'''
        in backup
    )


def test_recovery_library_supports_formats_one_and_two() -> None:
    recovery = (
        ROOT
        / "scripts"
        / "lib"
        / "backup-recovery.sh"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        '"$recovery_format" == \'1\' ||'
        in recovery
    )

    assert (
        '"$recovery_format" == \'2\''
        in recovery
    )

    assert (
        "atlas_sports_backend_recovery_validate_archive"
        in recovery
    )

    assert (
        "atlas_sports_backend_recovery_validate_staged"
        in recovery
    )


def test_format_two_restore_is_explicitly_fail_closed() -> None:
    recovery = (
        ROOT
        / "scripts"
        / "lib"
        / "backup-recovery.sh"
    ).read_text(
        encoding="utf-8"
    )

    restore = (
        ROOT
        / "scripts"
        / "commands"
        / "restore.sh"
    ).read_text(
        encoding="utf-8"
    )

    message = (
        "recovery format 2 contains native Sports backend state; "
        "live restore is not implemented."
    )

    assert message in recovery
    assert message in restore

    preflight = restore.index(
        "atlas_restore_require_production_preflight()"
    )

    guard = restore.index(
        message,
        preflight,
    )

    lock = restore.index(
        "atlas_deployment_acquire_lock",
        preflight,
    )

    assert guard < lock


def test_format_two_does_not_expand_canonical_surface_registry() -> None:
    recovery = (
        ROOT
        / "scripts"
        / "lib"
        / "backup-recovery.sh"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "expected 12 recovery surfaces"
        in recovery
    )

    assert (
        "restore plan expected 12 surfaces"
        in recovery
    )
