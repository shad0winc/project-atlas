"""Tests for the scheduled production cleanup callback."""

from __future__ import annotations

from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from atlas.cleanup.execution_models import (
    CleanupExecutionMode,
)
from atlas.cleanup.executor import (
    CleanupExecutionSummary,
    CleanupRunStatus,
)
from atlas.cleanup.scheduled_execution import (
    cleanup_execution_enabled,
    default_cleanup_state_root,
    execute_scheduled_cleanup,
    main,
)


SUMMARY = CleanupExecutionSummary(
    execution_id="cln_0123456789abcdef0123456789abcdef",
    provider="jellyfin",
    mode=CleanupExecutionMode.EXECUTE,
    status=CleanupRunStatus.SUCCESS,
    started_at="2026-09-21T20:00:00Z",
    completed_at="2026-09-21T20:00:01Z",
    total=2,
    planned=1,
    skipped=1,
    modified=1,
    errors=(),
)


def test_default_cleanup_state_root_uses_atlas_state_dir() -> None:
    assert default_cleanup_state_root(
        {
            "ATLAS_STATE_DIR": "/tmp/atlas-state",
        }
    ) == Path(
        "/tmp/atlas-state/cleanup"
    )


def test_default_cleanup_state_root_uses_canonical_default() -> None:
    assert default_cleanup_state_root(
        {}
    ) == Path(
        "/mnt/storage/configs/atlas/cleanup"
    )


def test_main_executes_once_and_renders_summary(monkeypatch) -> None:
    monkeypatch.setenv(
        "ATLAS_CLEANUP_EXECUTION_ENABLED",
        "true",
    )
    stdout = StringIO()
    stderr = StringIO()

    with patch(
        "atlas.cleanup.scheduled_execution."
        "execute_scheduled_cleanup",
        return_value=SUMMARY,
    ) as execute:
        result = main(
            [],
            stdout=stdout,
            stderr=stderr,
        )

    assert result == 0
    execute.assert_called_once_with()

    rendered = stdout.getvalue()

    assert '"mode": "execute"' in rendered
    assert '"provider": "jellyfin"' in rendered
    assert '"modified": 1' in rendered
    assert stderr.getvalue() == ""


def test_main_rejects_arguments_before_execution() -> None:
    stdout = StringIO()
    stderr = StringIO()

    with patch(
        "atlas.cleanup.scheduled_execution."
        "execute_scheduled_cleanup"
    ) as execute:
        result = main(
            ["unexpected"],
            stdout=stdout,
            stderr=stderr,
        )

    assert result == 2
    execute.assert_not_called()
    assert stdout.getvalue() == ""
    assert (
        "arguments are not supported"
        in stderr.getvalue()
    )


def test_main_fails_closed_on_execution_error(monkeypatch) -> None:
    monkeypatch.setenv(
        "ATLAS_CLEANUP_EXECUTION_ENABLED",
        "true",
    )
    stdout = StringIO()
    stderr = StringIO()

    with patch(
        "atlas.cleanup.scheduled_execution."
        "execute_scheduled_cleanup",
        side_effect=RuntimeError(
            "intent persistence unavailable"
        ),
    ) as execute:
        result = main(
            [],
            stdout=stdout,
            stderr=stderr,
        )

    assert result == 1
    execute.assert_called_once_with()
    assert stdout.getvalue() == ""
    assert (
        "Scheduled cleanup execution failed"
        in stderr.getvalue()
    )
    assert "intent persistence unavailable" not in stderr.getvalue()


def test_activation_requires_exact_true() -> None:
    assert cleanup_execution_enabled({}) is False
    assert cleanup_execution_enabled(
        {"ATLAS_CLEANUP_EXECUTION_ENABLED": ""}
    ) is False
    assert cleanup_execution_enabled(
        {"ATLAS_CLEANUP_EXECUTION_ENABLED": "TRUE"}
    ) is False
    assert cleanup_execution_enabled(
        {"ATLAS_CLEANUP_EXECUTION_ENABLED": "1"}
    ) is False
    assert cleanup_execution_enabled(
        {"ATLAS_CLEANUP_EXECUTION_ENABLED": "true"}
    ) is True


def test_main_without_activation_never_invokes_cleanup(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "ATLAS_CLEANUP_EXECUTION_ENABLED",
        raising=False,
    )
    stdout = StringIO()
    stderr = StringIO()

    with patch(
        "atlas.cleanup.scheduled_execution."
        "execute_scheduled_cleanup"
    ) as execute:
        result = main([], stdout=stdout, stderr=stderr)

    assert result == 1
    execute.assert_not_called()
    assert stdout.getvalue() == ""
    assert "not activated" in stderr.getvalue()


def test_direct_execution_without_activation_never_builds_workflow(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "ATLAS_CLEANUP_EXECUTION_ENABLED",
        raising=False,
    )

    with patch(
        "atlas.cleanup.scheduled_execution."
        "build_scheduled_cleanup_workflow"
    ) as build:
        try:
            execute_scheduled_cleanup()
        except RuntimeError as exc:
            assert "not activated" in str(exc)
        else:
            raise AssertionError("inactive direct execution was allowed")

    build.assert_not_called()


def test_main_non_success_summaries_return_failure(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_CLEANUP_EXECUTION_ENABLED",
        "true",
    )

    for status in (
        CleanupRunStatus.PARTIAL,
        CleanupRunStatus.FAILED,
    ):
        summary = replace(
            SUMMARY,
            status=status,
            modified=0,
            errors=("synthetic cleanup failure",),
        )
        stdout = StringIO()
        stderr = StringIO()

        with patch(
            "atlas.cleanup.scheduled_execution."
            "execute_scheduled_cleanup",
            return_value=summary,
        ) as execute:
            result = main(
                [],
                stdout=stdout,
                stderr=stderr,
            )

        assert result == 1
        execute.assert_called_once_with()
        assert f'"status": "{status.value}"' in stdout.getvalue()
        assert "did not complete successfully" in stderr.getvalue()
