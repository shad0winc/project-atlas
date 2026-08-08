"""Scheduled collection callback for Atlas Operations reports."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import os
from pathlib import Path
import sys
from typing import (
    Protocol,
    TextIO,
    runtime_checkable,
)

from atlas.operations import (
    FileOperationsRepository,
    HostOperationsContextProvider,
    OperationsReport,
    OperationsRepository,
    OperationsService,
)
from atlas.operations.collectors import (
    DockerCollector,
    SystemCollector,
)


@runtime_checkable
class OperationsCollectionService(Protocol):
    """Behavior required for scheduled Operations collection."""

    def collect(self) -> OperationsReport:
        """Collect one normalized Operations report."""

        ...


OperationsServiceFactory = Callable[
    [],
    OperationsCollectionService,
]
OperationsRepositoryFactory = Callable[[], OperationsRepository]


def default_service_factory() -> OperationsService:
    """Build the production Operations collection service."""

    return OperationsService(
        collectors=(
            SystemCollector(),
            DockerCollector(),
        ),
        context_provider=HostOperationsContextProvider(),
    )


def default_repository_factory() -> OperationsRepository:
    """Build the configured Operations report repository."""

    configured_root = os.environ.get(
        "ATLAS_OPERATIONS_DIRECTORY",
    )

    if configured_root is None:
        return FileOperationsRepository()

    normalized_root = configured_root.strip()

    if not normalized_root:
        raise ValueError(
            "ATLAS_OPERATIONS_DIRECTORY cannot be empty",
        )

    return FileOperationsRepository(
        normalized_root,
    )


def collect_and_persist(
    *,
    service_factory: OperationsServiceFactory = default_service_factory,
    repository_factory: OperationsRepositoryFactory = (
        default_repository_factory
    ),
) -> tuple[OperationsReport, Path]:
    """Collect and persist one immutable Operations report."""

    service = service_factory()

    if not isinstance(
        service,
        OperationsCollectionService,
    ):
        raise TypeError(
            "service_factory must return an "
            "Operations collection service",
        )

    repository = repository_factory()
    report = service.collect()
    snapshot_path = repository.save(report)

    if not isinstance(snapshot_path, Path):
        raise TypeError(
            "Operations repository save must return a Path",
        )

    return report, snapshot_path


def render_result(
    report: OperationsReport,
    snapshot_path: Path,
) -> str:
    """Render the stable scheduled-collection result."""

    if not isinstance(report, OperationsReport):
        raise TypeError(
            "report must be an OperationsReport",
        )

    if not isinstance(snapshot_path, Path):
        raise TypeError(
            "snapshot_path must be a Path",
        )

    payload = {
        "report_id": report.report_id,
        "generated_at": report.generated_at,
        "status": report.status.value,
        "score": report.score,
        "snapshot_path": str(snapshot_path),
    }

    return json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    service_factory: OperationsServiceFactory = default_service_factory,
    repository_factory: OperationsRepositoryFactory = (
        default_repository_factory
    ),
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Execute one scheduled Operations collection."""

    arguments = tuple(
        sys.argv[1:]
        if argv is None
        else argv
    )
    output = stdout or sys.stdout
    errors = stderr or sys.stderr

    if arguments:
        print(
            "Operations scheduled collection failed: "
            "arguments are not supported",
            file=errors,
        )
        return 2

    try:
        report, snapshot_path = collect_and_persist(
            service_factory=service_factory,
            repository_factory=repository_factory,
        )
    except Exception as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        print(
            "Operations scheduled collection failed: "
            f"{detail}",
            file=errors,
        )
        return 1

    print(
        render_result(
            report,
            snapshot_path,
        ),
        file=output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
