"""Assemble normalized Service Lifecycle runtime snapshots."""

from __future__ import annotations

from datetime import UTC, datetime

from .models import ServiceLifecycleError
from .provider import ServiceLifecycleProvider
from .services.lifecycle import ServiceLifecycleService
from .services.maintenance import (
    ServiceMaintenanceHistoryService,
)
from .services.updates import ServiceUpdateService


RUNTIME_SNAPSHOT_SCHEMA_VERSION = 1


def build_runtime_snapshot(
    provider: ServiceLifecycleProvider,
    *,
    generated_at: str | None = None,
) -> dict[str, object]:
    """Return one normalized read-only Service Lifecycle snapshot."""

    if not isinstance(provider, ServiceLifecycleProvider):
        raise ServiceLifecycleError(
            "provider must implement ServiceLifecycleProvider"
        )

    lifecycle = ServiceLifecycleService(provider)
    update_service = ServiceUpdateService(lifecycle)
    history_service = ServiceMaintenanceHistoryService(
        lifecycle
    )

    services = lifecycle.list_services()

    entries: list[dict[str, object]] = []

    for service in services:
        runtime = lifecycle.inspect_runtime(
            service.identifier
        )
        health = lifecycle.inspect_health(
            service.identifier
        )
        update = update_service.inspect_update(
            service.identifier
        )

        entries.append(
            {
                "service": service.to_dict(),
                "runtime": runtime.to_dict(),
                "health": health.to_dict(),
                "update": update.to_dict(),
            }
        )

    history = history_service.inspect_history()

    timestamp = (
        generated_at
        if generated_at is not None
        else datetime.now(UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )

    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ServiceLifecycleError(
            "generated_at must be non-empty text"
        )

    return {
        "schema_version": (
            RUNTIME_SNAPSHOT_SCHEMA_VERSION
        ),
        "generated_at": timestamp.strip(),
        "provider": _snapshot_provider(
            services,
            history.provider,
        ),
        "services": entries,
        "history": history.to_dict(),
    }


def _snapshot_provider(
    services: tuple,
    history_provider: str,
) -> str:
    providers = sorted(
        {
            service.provider
            for service in services
        }
    )

    if len(providers) == 1:
        return providers[0]

    if len(providers) > 1:
        return "mixed"

    if (
        isinstance(history_provider, str)
        and history_provider.strip()
    ):
        return history_provider.strip()

    return "unknown"
