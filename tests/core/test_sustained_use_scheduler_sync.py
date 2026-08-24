"""Scheduler sync integration tests for Q.6 sustained-use."""

from __future__ import annotations

from pathlib import Path

import atlas.scheduler_cli as scheduler_cli


def test_unqualified_sync_registers_both_core_jobs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, object]] = []

    scheduler = object()

    def fake_module_sync(
        received_scheduler,
        project_directory,
        registry_file,
        module_name,
    ):
        calls.append(
            (
                "modules",
                (
                    received_scheduler,
                    project_directory,
                    registry_file,
                    module_name,
                ),
            )
        )

        return {
            "registered": [
                "sports.sync",
            ],
            "removed": [
                "sports.old",
            ],
            "skipped": [
                "sports.disabled",
            ],
        }

    def fake_operations(received_scheduler):
        calls.append(
            (
                "operations",
                received_scheduler,
            )
        )

        return {
            "name": "operations.collect",
        }

    def fake_sustained_use(received_scheduler):
        calls.append(
            (
                "sustained-use",
                received_scheduler,
            )
        )

        return {
            "name": "sustained-use.sample",
        }

    monkeypatch.setattr(
        scheduler_cli,
        "sync_module_jobs",
        fake_module_sync,
    )
    monkeypatch.setattr(
        scheduler_cli,
        "register_operations_collection",
        fake_operations,
    )
    monkeypatch.setattr(
        scheduler_cli,
        "register_sustained_use_sampling",
        fake_sustained_use,
    )

    project = tmp_path / "project"
    registry = project / "config" / "modules" / "modules.conf"

    result = scheduler_cli._sync_scheduler_jobs(
        scheduler,
        project,
        registry,
        None,
    )

    assert result == {
        "registered": [
            "operations.collect",
            "sports.sync",
            "sustained-use.sample",
        ],
        "removed": [
            "sports.old",
        ],
        "skipped": [
            "sports.disabled",
        ],
    }

    assert calls == [
        (
            "modules",
            (
                scheduler,
                project,
                registry,
                None,
            ),
        ),
        (
            "operations",
            scheduler,
        ),
        (
            "sustained-use",
            scheduler,
        ),
    ]


def test_targeted_module_sync_skips_all_core_jobs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    scheduler = object()

    expected = {
        "registered": [
            "sports.sync",
        ],
        "removed": [],
        "skipped": [],
    }

    def fake_module_sync(
        received_scheduler,
        project_directory,
        registry_file,
        module_name,
    ):
        assert received_scheduler is scheduler
        assert module_name == "sports"

        return expected

    def core_job_must_not_run(*args, **kwargs):
        raise AssertionError(
            "core Scheduler registration must not run "
            "during targeted module sync"
        )

    monkeypatch.setattr(
        scheduler_cli,
        "sync_module_jobs",
        fake_module_sync,
    )
    monkeypatch.setattr(
        scheduler_cli,
        "register_operations_collection",
        core_job_must_not_run,
    )
    monkeypatch.setattr(
        scheduler_cli,
        "register_sustained_use_sampling",
        core_job_must_not_run,
    )

    project = tmp_path / "project"
    registry = project / "config" / "modules" / "modules.conf"

    result = scheduler_cli._sync_scheduler_jobs(
        scheduler,
        project,
        registry,
        "sports",
    )

    assert result is expected


def test_core_registration_result_is_deduplicated(
    monkeypatch,
    tmp_path: Path,
) -> None:
    scheduler = object()

    monkeypatch.setattr(
        scheduler_cli,
        "sync_module_jobs",
        lambda *args, **kwargs: {
            "registered": [
                "operations.collect",
                "sustained-use.sample",
            ],
            "removed": [],
            "skipped": [],
        },
    )

    monkeypatch.setattr(
        scheduler_cli,
        "register_operations_collection",
        lambda received_scheduler: {
            "name": "operations.collect",
        },
    )

    monkeypatch.setattr(
        scheduler_cli,
        "register_sustained_use_sampling",
        lambda received_scheduler: {
            "name": "sustained-use.sample",
        },
    )

    result = scheduler_cli._sync_scheduler_jobs(
        scheduler,
        tmp_path,
        tmp_path / "modules.conf",
        None,
    )

    assert result["registered"] == [
        "operations.collect",
        "sustained-use.sample",
    ]
