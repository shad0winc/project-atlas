"""Tests for durable cleanup deletion-intent persistence."""

from __future__ import annotations

import errno
from datetime import datetime, timedelta, timezone

import pytest

from atlas.cleanup.deletion_intent_repository import (
    CleanupDeletionIntentConflictError,
    CleanupDeletionIntentRepositoryError,
    JsonCleanupDeletionIntentRepository,
)
from atlas.cleanup.deletion_intents import (
    CleanupDeletionIntent,
)


EXECUTION_ID = (
    "cln_0123456789abcdef"
    "0123456789abcdef"
)
OTHER_EXECUTION_ID = (
    "cln_fedcba9876543210"
    "fedcba9876543210"
)
CREATED_AT = datetime(
    2026,
    9,
    9,
    23,
    30,
    tzinfo=timezone.utc,
)


def make_intent(
    **overrides: object,
) -> CleanupDeletionIntent:
    values: dict[str, object] = {
        "execution_id": EXECUTION_ID,
        "provider": "jellyfin",
        "item_id": "movie-1",
        "created_at": CREATED_AT,
    }
    values.update(overrides)

    return CleanupDeletionIntent(**values)  # type: ignore[arg-type]


def test_missing_repository_initializes_empty(
    tmp_path,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )

    assert repository.list() == ()
    assert repository.registry_file.exists()


def test_save_and_get_pending_intent(
    tmp_path,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )
    intent = make_intent()

    assert repository.save(intent) == intent
    assert (
        repository.get(
            "jellyfin",
            "movie-1",
        )
        == intent
    )


def test_pending_intent_survives_repository_restart(
    tmp_path,
) -> None:
    first = JsonCleanupDeletionIntentRepository(
        tmp_path
    )
    intent = make_intent()
    first.save(intent)

    second = JsonCleanupDeletionIntentRepository(
        tmp_path
    )

    assert second.list() == (intent,)
    assert (
        second.get(
            "jellyfin",
            "movie-1",
        )
        == intent
    )


def test_provider_item_conflict_blocks_replay(
    tmp_path,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )
    original = make_intent()
    repository.save(original)

    replay = make_intent(
        execution_id=OTHER_EXECUTION_ID,
        created_at=CREATED_AT + timedelta(seconds=1),
    )

    with pytest.raises(
        CleanupDeletionIntentConflictError,
        match="already exists",
    ):
        repository.save(replay)

    assert repository.list() == (original,)


def test_same_item_id_on_different_provider_is_allowed(
    tmp_path,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )

    first = make_intent()
    second = make_intent(
        execution_id=OTHER_EXECUTION_ID,
        provider="plex",
    )

    repository.save(first)
    repository.save(second)

    assert repository.list() == (
        first,
        second,
    )


def test_remove_clears_only_matching_replay_barrier(
    tmp_path,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )

    first = make_intent()
    second = make_intent(
        execution_id=OTHER_EXECUTION_ID,
        item_id="movie-2",
        created_at=CREATED_AT + timedelta(seconds=1),
    )

    repository.save(first)
    repository.save(second)

    assert (
        repository.remove(
            "jellyfin",
            "movie-1",
        )
        == first
    )

    assert repository.get(
        "jellyfin",
        "movie-1",
    ) is None
    assert repository.list() == (second,)


def test_remove_missing_intent_fails_closed(
    tmp_path,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )

    with pytest.raises(
        CleanupDeletionIntentRepositoryError,
        match="not found",
    ):
        repository.remove(
            "jellyfin",
            "missing",
        )


def test_failed_persistence_does_not_replace_existing_registry(
    tmp_path,
    monkeypatch,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )
    original = make_intent()
    repository.save(original)

    before = repository.registry_file.read_text(
        encoding="utf-8"
    )

    def fail_write(*args, **kwargs) -> None:
        raise OSError(
            errno.ENOSPC,
            "No space left on device",
        )

    monkeypatch.setattr(
        "atlas.cleanup.deletion_intent_repository.os.replace",
        fail_write,
    )

    with pytest.raises(
        CleanupDeletionIntentRepositoryError,
        match="unable to durably persist",
    ):
        repository.save(
            make_intent(
                execution_id=OTHER_EXECUTION_ID,
                item_id="movie-2",
                created_at=(
                    CREATED_AT
                    + timedelta(seconds=1)
                ),
            )
        )

    after = repository.registry_file.read_text(
        encoding="utf-8"
    )

    assert after == before


def test_rejects_duplicate_targets_in_registry(
    tmp_path,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )
    repository.initialize()

    payload = make_intent().to_dict()

    repository.registry_file.write_text(
        __import__("json").dumps(
            {
                "schema_version": 1,
                "intents": [
                    payload,
                    payload,
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        CleanupDeletionIntentRepositoryError,
        match="duplicate provider item",
    ):
        repository.list()


def test_durable_write_fsyncs_file_before_replace(
    tmp_path,
    monkeypatch,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )

    calls: list[str] = []
    real_fsync = __import__("os").fsync
    real_replace = __import__("os").replace

    def observe_fsync(descriptor: int) -> None:
        calls.append("fsync")
        real_fsync(descriptor)

    def observe_replace(source, destination) -> None:
        calls.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr(
        "atlas.cleanup.deletion_intent_repository.os.fsync",
        observe_fsync,
    )
    monkeypatch.setattr(
        "atlas.cleanup.deletion_intent_repository.os.replace",
        observe_replace,
    )

    repository.save(make_intent())

    assert "replace" in calls
    replace_index = calls.index("replace")

    assert "fsync" in calls[:replace_index]


def test_durable_write_syncs_directory_after_replace(
    tmp_path,
    monkeypatch,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )
    repository.initialize()

    calls: list[str] = []
    real_replace = __import__("os").replace
    real_sync_directory = repository._sync_directory

    def observe_replace(source, destination) -> None:
        calls.append("replace")
        real_replace(source, destination)

    def observe_sync_directory(directory) -> None:
        calls.append("directory-fsync")
        real_sync_directory(directory)

    monkeypatch.setattr(
        "atlas.cleanup.deletion_intent_repository.os.replace",
        observe_replace,
    )
    monkeypatch.setattr(
        repository,
        "_sync_directory",
        observe_sync_directory,
    )

    repository.save(make_intent())

    assert calls == [
        "replace",
        "directory-fsync",
    ]


def test_directory_sync_failure_is_persistence_failure(
    tmp_path,
    monkeypatch,
) -> None:
    repository = JsonCleanupDeletionIntentRepository(
        tmp_path
    )

    def fail_sync(directory) -> None:
        raise OSError(
            errno.EIO,
            "directory sync failed",
        )

    monkeypatch.setattr(
        repository,
        "_sync_directory",
        fail_sync,
    )

    with pytest.raises(
        CleanupDeletionIntentRepositoryError,
        match="unable to durably persist",
    ):
        repository.save(make_intent())
