"""Scheduled production cleanup execution for Project Atlas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import sys
from typing import TextIO

from atlas.cleanup.audit import JsonlCleanupAuditWriter
from atlas.cleanup.audit_config import (
    DEFAULT_ATLAS_STATE_DIR,
    default_cleanup_audit_path,
)
from atlas.cleanup.default_executor import DefaultCleanupExecutor
from atlas.cleanup.deletion_intent_repository import (
    JsonCleanupDeletionIntentRepository,
)
from atlas.cleanup.execution_models import CleanupExecutionMode
from atlas.cleanup.execution_service import CleanupExecutionService
from atlas.cleanup.executor import CleanupExecutionSummary
from atlas.cleanup.scanner import CleanupScanner
from atlas.cleanup.service import CleanupService
from atlas.cleanup.workflow import CleanupWorkflowService
from atlas.media.jellyfin import (
    JellyfinProvider,
    default_jellyfin_provider,
)


DEFAULT_PAGE_SIZE = 200
DEFAULT_CLEANUP_STATE_RELATIVE_PATH = Path("cleanup")


def default_cleanup_state_root(
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Resolve persistent state for destructive cleanup coordination."""

    environ = (
        environment
        if environment is not None
        else os.environ
    )

    configured = environ.get(
        "ATLAS_STATE_DIR",
        "",
    ).strip()

    state_root = (
        Path(configured)
        if configured
        else DEFAULT_ATLAS_STATE_DIR
    )

    return (
        state_root
        / DEFAULT_CLEANUP_STATE_RELATIVE_PATH
    )


def build_scheduled_cleanup_workflow(
    *,
    provider: JellyfinProvider | None = None,
    cleanup_service: CleanupService | None = None,
) -> tuple[JellyfinProvider, CleanupWorkflowService]:
    """Build the production live-cleanup dependency graph."""

    resolved_provider = (
        provider
        if provider is not None
        else default_jellyfin_provider()
    )

    resolved_cleanup_service = (
        cleanup_service
        if cleanup_service is not None
        else CleanupService()
    )

    scanner = CleanupScanner(
        resolved_cleanup_service,
    )

    planner = CleanupExecutionService()

    audit_writer = JsonlCleanupAuditWriter(
        default_cleanup_audit_path(),
        durable=True,
    )

    deletion_intents = (
        JsonCleanupDeletionIntentRepository(
            default_cleanup_state_root(),
        )
    )

    executor = DefaultCleanupExecutor(
        provider=resolved_provider,
        audit_writer=audit_writer,
        deletion_intent_repository=deletion_intents,
        cleanup_service=resolved_cleanup_service,
    )

    workflow = CleanupWorkflowService(
        scanner=scanner,
        planner=planner,
        executor=executor,
    )

    return resolved_provider, workflow


def execute_scheduled_cleanup(
    *,
    provider: JellyfinProvider | None = None,
    cleanup_service: CleanupService | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CleanupExecutionSummary:
    """Execute one production cleanup cycle."""

    resolved_provider, workflow = (
        build_scheduled_cleanup_workflow(
            provider=provider,
            cleanup_service=cleanup_service,
        )
    )

    return workflow.execute(
        resolved_provider,
        page_size=page_size,
        mode=CleanupExecutionMode.EXECUTE,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Execute one scheduled production cleanup cycle."""

    arguments = tuple(
        sys.argv[1:]
        if argv is None
        else argv
    )

    output = stdout or sys.stdout
    errors = stderr or sys.stderr

    if arguments:
        print(
            "Scheduled cleanup execution failed: "
            "arguments are not supported",
            file=errors,
        )
        return 2

    try:
        summary = execute_scheduled_cleanup()
    except Exception as exc:
        detail = (
            str(exc).strip()
            or exc.__class__.__name__
        )

        print(
            "Scheduled cleanup execution failed: "
            f"{detail}",
            file=errors,
        )
        return 1

    print(
        json.dumps(
            summary.to_dict(),
            indent=2,
            sort_keys=True,
        ),
        file=output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
