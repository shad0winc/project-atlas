"""Tests for the scheduled production cleanup callback."""

from __future__ import annotations

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
    default_cleanup_state_root,
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


def test_main_executes_once_and_renders_summary() -> None:
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


def test_main_fails_closed_on_execution_error() -> None:
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
        "intent persistence unavailable"
        in stderr.getvalue()
    )
