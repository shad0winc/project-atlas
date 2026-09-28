"""Combine observations from independently deployed Compose projects."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import ServiceLifecycleError


def merge_runtime_snapshots(
    core: Mapping[str, Any],
    sports_backend: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish both projects as one snapshot while retaining core history."""

    if core.get("schema_version") != 1 or sports_backend.get("schema_version") != 1:
        raise ServiceLifecycleError("Service Lifecycle snapshot schema mismatch")

    identifiers: set[str] = set()
    entries: list[dict[str, Any]] = []
    for snapshot in (core, sports_backend):
        source_entries = snapshot.get("services")
        if not isinstance(source_entries, list):
            raise ServiceLifecycleError("Service Lifecycle snapshot services are invalid")
        for entry in source_entries:
            if not isinstance(entry, dict):
                raise ServiceLifecycleError("Service Lifecycle snapshot entry is invalid")
            service = entry.get("service")
            identifier = service.get("identifier") if isinstance(service, dict) else None
            if not isinstance(identifier, str) or not identifier:
                raise ServiceLifecycleError("Service Lifecycle service identifier is invalid")
            if identifier in identifiers:
                raise ServiceLifecycleError(
                    f"duplicate Service Lifecycle service identifier: {identifier}"
                )
            identifiers.add(identifier)
            entries.append(entry)

    for expected in ("atlas-dispatcharr", "atlas-teamarr"):
        if expected not in identifiers:
            raise ServiceLifecycleError(f"Sports Backend service missing: {expected}")

    result = dict(core)
    result["services"] = sorted(
        entries, key=lambda entry: entry["service"]["identifier"]
    )
    # Both observations share the same read-only provider type. Core's
    # maintenance history remains authoritative for existing services.
    return result
