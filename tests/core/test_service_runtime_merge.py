"""Service snapshots must preserve observations from both Compose projects."""

from __future__ import annotations

import pytest

from atlas.service_lifecycle.models import ServiceLifecycleError
from atlas.service_lifecycle.runtime_snapshot_merge import (
    merge_runtime_snapshots,
    sports_backend_installed,
)


def snapshot(*names: str) -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-09-28T23:00:00Z",
        "provider": "docker-compose",
        "services": [{"service": {"identifier": name}} for name in names],
        "history": {"provider": "docker-compose", "records": []},
    }


def test_combines_projects_and_preserves_core_history() -> None:
    core = snapshot("jellyfin")
    core["history"]["records"] = [{"service_identifier": "jellyfin"}]
    backend = snapshot("atlas-dispatcharr", "atlas-teamarr")

    combined = merge_runtime_snapshots(core, backend)

    assert [row["service"]["identifier"] for row in combined["services"]] == [
        "atlas-dispatcharr", "atlas-teamarr", "jellyfin"
    ]
    assert combined["history"] == core["history"]
    assert len(core["services"]) == 1


def test_duplicate_service_refuses_publication() -> None:
    with pytest.raises(ServiceLifecycleError, match="duplicate"):
        merge_runtime_snapshots(
            snapshot("atlas-dispatcharr"),
            snapshot("atlas-dispatcharr", "atlas-teamarr"),
        )


def test_missing_backend_service_refuses_partial_publication() -> None:
    with pytest.raises(ServiceLifecycleError, match="atlas-teamarr"):
        merge_runtime_snapshots(snapshot("jellyfin"), snapshot("atlas-dispatcharr"))


def test_optional_backend_absence() -> None:
    assert not sports_backend_installed(())


def test_installed_backend_including_stopped_containers() -> None:
    assert sports_backend_installed(("atlas-dispatcharr", "atlas-teamarr"))


def test_partial_backend_is_not_silently_hidden() -> None:
    with pytest.raises(ServiceLifecycleError, match="partial"):
        sports_backend_installed(("atlas-dispatcharr",))
