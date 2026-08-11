"""Contract tests for the Atlas media-request repository."""

from __future__ import annotations

import errno
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from atlas.media_requests import (
    JsonMediaRequestRepository,
    MediaRequest,
    MediaRequestRepositoryConflictError,
    MediaRequestRepositoryError,
    MediaRequestStatus,
    MediaRequestType,
    SCHEMA_VERSION,
)


CREATED_AT = "2026-08-02T20:00:00Z"


def make_request(**overrides: object) -> MediaRequest:
    values: dict[str, object] = {
        "request_id": "request-001",
        "user_id": "user-001",
        "media_type": MediaRequestType.MOVIE,
        "provider": "jellyseerr",
        "provider_request_id": "provider-request-001",
        "provider_media_id": "tmdb:157336",
        "title": "Interstellar",
        "year": 2014,
        "status": MediaRequestStatus.PENDING,
        "created_at": CREATED_AT,
    }
    values.update(overrides)
    return MediaRequest(**values)


@pytest.fixture
def repository(
    tmp_path: Path,
) -> JsonMediaRequestRepository:
    return JsonMediaRequestRepository(tmp_path / "requests")


def test_initialize_creates_schema_versioned_registry(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.initialize()

    assert repository.root.is_dir()
    assert json.loads(
        repository.registry_file.read_text(encoding="utf-8")
    ) == {
        "schema_version": SCHEMA_VERSION,
        "requests": {},
    }


def test_initialize_preserves_existing_registry(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.initialize()
    original = repository.registry_file.read_text(encoding="utf-8")

    repository.initialize()

    assert repository.registry_file.read_text(encoding="utf-8") == original


def test_save_and_get_round_trip_normalized_model(
    repository: JsonMediaRequestRepository,
) -> None:
    request = make_request()

    assert repository.save(request) is request
    assert repository.get(" request-001 ") == request


def test_save_persists_serialized_contract(
    repository: JsonMediaRequestRepository,
) -> None:
    request = make_request()
    repository.save(request)

    payload = json.loads(
        repository.registry_file.read_text(encoding="utf-8")
    )

    assert payload["requests"]["request-001"] == request.to_dict()


def test_save_requires_media_request(
    repository: JsonMediaRequestRepository,
) -> None:
    with pytest.raises(
        MediaRequestRepositoryError,
        match="request must be a MediaRequest",
    ):
        repository.save(object())  # type: ignore[arg-type]


def test_save_rejects_duplicate_request_id(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.save(make_request())

    with pytest.raises(
        MediaRequestRepositoryError,
        match="already exists",
    ):
        repository.save(
            make_request(
                provider_request_id="provider-request-002",
            )
        )


def test_save_rejects_duplicate_provider_request_identity(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.save(make_request())

    with pytest.raises(
        MediaRequestRepositoryError,
        match="provider request already exists",
    ):
        repository.save(
            make_request(
                request_id="request-002",
                provider_media_id="tmdb:603",
            )
        )


def test_same_provider_request_id_is_allowed_for_different_provider(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.save(make_request())

    second = make_request(
        request_id="request-002",
        provider="sports",
        provider_media_id="event:001",
        media_type="sports",
        title="Team A vs Team B",
    )

    assert repository.save(second) == second


def test_requests_without_provider_request_id_can_repeat(
    repository: JsonMediaRequestRepository,
) -> None:
    first = make_request(provider_request_id=None)
    second = make_request(
        request_id="request-002",
        provider_request_id=None,
    )

    repository.save(first)
    repository.save(second)

    assert repository.list() == (first, second)


def test_strict_save_rejects_active_duplicate_across_users(
    repository: JsonMediaRequestRepository,
) -> None:
    first = make_request(
        provider_request_id=None,
    )
    second = make_request(
        request_id="request-002",
        user_id="user-002",
        provider_request_id=None,
        title="Same provider target, different title",
        year=2015,
    )

    repository.save_if_no_active_conflict(first)

    with pytest.raises(
        MediaRequestRepositoryConflictError,
        match="active media request conflicts",
    ):
        repository.save_if_no_active_conflict(second)

    assert repository.list() == (first,)


def test_strict_save_treats_jellyseerr_anime_movie_as_movie(
    repository: JsonMediaRequestRepository,
) -> None:
    first = make_request(
        provider_request_id=None,
        media_type=MediaRequestType.MOVIE,
    )
    second = make_request(
        request_id="request-002",
        user_id="user-002",
        provider_request_id=None,
        media_type=MediaRequestType.ANIME_MOVIE,
    )

    repository.save_if_no_active_conflict(first)

    with pytest.raises(
        MediaRequestRepositoryConflictError,
        match="active media request conflicts",
    ):
        repository.save_if_no_active_conflict(second)


@pytest.mark.parametrize(
    ("existing_season", "candidate_season"),
    (
        (None, None),
        (None, 1),
        (1, None),
        (1, 1),
    ),
)
def test_strict_save_rejects_overlapping_tv_seasons(
    repository: JsonMediaRequestRepository,
    existing_season: int | None,
    candidate_season: int | None,
) -> None:
    first = make_request(
        provider_request_id=None,
        media_type=MediaRequestType.TV,
        season_number=existing_season,
    )
    second = make_request(
        request_id="request-002",
        user_id="user-002",
        provider_request_id=None,
        media_type=MediaRequestType.ANIME_TV,
        season_number=candidate_season,
    )

    repository.save_if_no_active_conflict(first)

    with pytest.raises(
        MediaRequestRepositoryConflictError,
        match="active media request conflicts",
    ):
        repository.save_if_no_active_conflict(second)


def test_strict_save_allows_different_explicit_tv_seasons(
    repository: JsonMediaRequestRepository,
) -> None:
    first = make_request(
        provider_request_id=None,
        media_type=MediaRequestType.TV,
        season_number=1,
    )
    second = make_request(
        request_id="request-002",
        user_id="user-002",
        provider_request_id=None,
        media_type=MediaRequestType.ANIME_TV,
        season_number=2,
    )

    repository.save_if_no_active_conflict(first)
    repository.save_if_no_active_conflict(second)

    assert repository.list() == (first, second)


def test_strict_save_allows_target_after_terminal_history(
    repository: JsonMediaRequestRepository,
) -> None:
    first = make_request(
        provider_request_id=None,
        status=MediaRequestStatus.CANCELLED,
    )
    second = make_request(
        request_id="request-002",
        user_id="user-002",
        provider_request_id=None,
    )

    repository.save(first)
    repository.save_if_no_active_conflict(second)

    assert repository.list() == (first, second)


def test_strict_save_acquires_process_lock(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.initialize()

    request = make_request(
        provider_request_id=None,
    )

    with patch(
        "atlas.media_requests.repository.fcntl.flock"
    ) as flock:
        repository.save_if_no_active_conflict(
            request
        )

    assert flock.call_count == 2
    assert flock.call_args_list[0].args[1] == (
        __import__("fcntl").LOCK_EX
    )
    assert flock.call_args_list[1].args[1] == (
        __import__("fcntl").LOCK_UN
    )


def test_all_registry_mutations_acquire_process_lock(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.initialize()

    original = make_request(
        provider_request_id=None,
    )
    replacement = make_request(
        provider_request_id=None,
        status=MediaRequestStatus.APPROVED,
        updated_at="2026-08-02T20:30:00Z",
    )

    with patch(
        "atlas.media_requests.repository.fcntl.flock"
    ) as flock:
        repository.save(original)
        repository.replace(replacement)
        repository.delete(original.request_id)

    operations = [
        call.args[1]
        for call in flock.call_args_list
    ]

    assert operations == [
        __import__("fcntl").LOCK_EX,
        __import__("fcntl").LOCK_UN,
        __import__("fcntl").LOCK_EX,
        __import__("fcntl").LOCK_UN,
        __import__("fcntl").LOCK_EX,
        __import__("fcntl").LOCK_UN,
    ]


def test_replace_updates_existing_request(
    repository: JsonMediaRequestRepository,
) -> None:
    original = make_request()
    replacement = make_request(
        status="approved",
        updated_at="2026-08-02T20:30:00Z",
    )
    repository.save(original)

    assert repository.replace(replacement) == replacement
    assert repository.get("request-001") == replacement


def test_replace_requires_media_request(
    repository: JsonMediaRequestRepository,
) -> None:
    with pytest.raises(
        MediaRequestRepositoryError,
        match="request must be a MediaRequest",
    ):
        repository.replace(object())  # type: ignore[arg-type]


def test_replace_rejects_missing_request(
    repository: JsonMediaRequestRepository,
) -> None:
    with pytest.raises(
        MediaRequestRepositoryError,
        match="not found",
    ):
        repository.replace(make_request())


def test_replace_preserves_unrelated_requests(
    repository: JsonMediaRequestRepository,
) -> None:
    first = make_request()
    second = make_request(
        request_id="request-002",
        provider_request_id="provider-request-002",
        provider_media_id="tmdb:603",
        title="The Matrix",
    )
    updated_first = make_request(
        status="searching",
        updated_at="2026-08-02T20:30:00Z",
    )

    repository.save(first)
    repository.save(second)
    repository.replace(updated_first)

    assert repository.list() == (
        updated_first,
        second,
    )


def test_replace_allows_existing_provider_identity_for_same_request(
    repository: JsonMediaRequestRepository,
) -> None:
    original = make_request()
    replacement = make_request(
        status="downloading",
        updated_at="2026-08-02T20:30:00Z",
    )
    repository.save(original)

    assert repository.replace(replacement) == replacement


def test_replace_rejects_provider_request_collision(
    repository: JsonMediaRequestRepository,
) -> None:
    first = make_request()
    second = make_request(
        request_id="request-002",
        provider_request_id="provider-request-002",
        provider_media_id="tmdb:603",
    )
    collision = make_request(
        request_id="request-002",
        provider_request_id="provider-request-001",
        provider_media_id="tmdb:603",
        updated_at="2026-08-02T20:30:00Z",
    )

    repository.save(first)
    repository.save(second)

    with pytest.raises(
        MediaRequestRepositoryError,
        match="provider request already exists",
    ):
        repository.replace(collision)

    assert repository.get("request-002") == second


def test_replace_can_transition_request_to_available(
    repository: JsonMediaRequestRepository,
) -> None:
    original = make_request()
    available = make_request(
        status="available",
        updated_at="2026-08-02T21:00:00Z",
        available_at="2026-08-02T21:00:00Z",
    )
    repository.save(original)

    repository.replace(available)

    stored = repository.get("request-001")
    assert stored.status is MediaRequestStatus.AVAILABLE
    assert stored.available_at == "2026-08-02T21:00:00Z"
    assert stored.terminal is True


def test_replace_uses_shared_atomic_json_helper(
    repository: JsonMediaRequestRepository,
) -> None:
    original = make_request()
    replacement = make_request(
        status="approved",
        updated_at="2026-08-02T20:30:00Z",
    )
    repository.save(original)

    with patch(
        "atlas.media_requests.repository.write_json_atomic",
    ) as writer:
        repository.replace(replacement)

    writer.assert_called_once()
    destination, payload = writer.call_args.args
    assert destination == repository.registry_file
    assert payload["requests"]["request-001"] == replacement.to_dict()


def test_replace_preserves_deterministic_registry_order(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.save(
        make_request(
            request_id="request-z",
            provider_request_id="provider-z",
        )
    )
    repository.save(
        make_request(
            request_id="request-a",
            provider_request_id="provider-a",
        )
    )
    repository.replace(
        make_request(
            request_id="request-z",
            provider_request_id="provider-z",
            status="approved",
            updated_at="2026-08-02T20:30:00Z",
        )
    )

    raw = repository.registry_file.read_text(encoding="utf-8")
    assert raw.index('"request-a"') < raw.index('"request-z"')


def test_replace_rejects_corrupt_registry_without_overwrite(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.initialize()
    repository.registry_file.write_text(
        "{invalid",
        encoding="utf-8",
    )

    with pytest.raises(
        MediaRequestRepositoryError,
        match="invalid JSON",
    ):
        repository.replace(make_request())

    assert repository.registry_file.read_text(
        encoding="utf-8"
    ) == "{invalid"


def test_get_rejects_missing_request(
    repository: JsonMediaRequestRepository,
) -> None:
    with pytest.raises(
        MediaRequestRepositoryError,
        match="not found",
    ):
        repository.get("missing-request")


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, True, object(), "bad/request"],
)
def test_get_rejects_invalid_request_identity(
    repository: JsonMediaRequestRepository,
    value: object,
) -> None:
    with pytest.raises(
        MediaRequestRepositoryError,
        match="request_id",
    ):
        repository.get(value)


def test_list_returns_deterministic_chronological_order(
    repository: JsonMediaRequestRepository,
) -> None:
    later = make_request(
        request_id="request-003",
        provider_request_id="provider-request-003",
        created_at="2026-08-02T22:00:00Z",
    )
    same_time_second = make_request(
        request_id="request-002",
        provider_request_id="provider-request-002",
    )
    same_time_first = make_request(
        request_id="request-001",
        provider_request_id="provider-request-001",
    )

    repository.save(later)
    repository.save(same_time_second)
    repository.save(same_time_first)

    assert repository.list() == (
        same_time_first,
        same_time_second,
        later,
    )


def test_list_by_user_returns_only_owned_requests(
    repository: JsonMediaRequestRepository,
) -> None:
    first = make_request()
    second = make_request(
        request_id="request-002",
        user_id="user-002",
        provider_request_id="provider-request-002",
    )
    third = make_request(
        request_id="request-003",
        provider_request_id="provider-request-003",
        created_at="2026-08-02T21:00:00Z",
    )

    for request in (third, second, first):
        repository.save(request)

    assert repository.list_by_user(" user-001 ") == (
        first,
        third,
    )


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, True, object(), "bad/user"],
)
def test_list_by_user_rejects_invalid_identity(
    repository: JsonMediaRequestRepository,
    value: object,
) -> None:
    with pytest.raises(
        MediaRequestRepositoryError,
        match="user_id",
    ):
        repository.list_by_user(value)


def test_find_by_provider_request_returns_match(
    repository: JsonMediaRequestRepository,
) -> None:
    request = make_request()
    repository.save(request)

    assert repository.find_by_provider_request(
        " Jellyseerr ",
        " provider-request-001 ",
    ) == request


def test_find_by_provider_request_returns_none_when_missing(
    repository: JsonMediaRequestRepository,
) -> None:
    assert repository.find_by_provider_request(
        "jellyseerr",
        "missing",
    ) is None


@pytest.mark.parametrize(
    ("provider", "provider_request_id"),
    [
        ("", "1"),
        (None, "1"),
        ("bad/provider", "1"),
        ("jellyseerr", ""),
        ("jellyseerr", None),
        ("jellyseerr", "bad/request"),
    ],
)
def test_find_by_provider_request_rejects_invalid_inputs(
    repository: JsonMediaRequestRepository,
    provider: object,
    provider_request_id: object,
) -> None:
    with pytest.raises(MediaRequestRepositoryError):
        repository.find_by_provider_request(
            provider,
            provider_request_id,
        )


def test_delete_returns_request_and_removes_record(
    repository: JsonMediaRequestRepository,
) -> None:
    request = make_request()
    repository.save(request)

    assert repository.delete("request-001") == request
    assert repository.list() == ()

    with pytest.raises(
        MediaRequestRepositoryError,
        match="not found",
    ):
        repository.get("request-001")


def test_delete_rejects_missing_request(
    repository: JsonMediaRequestRepository,
) -> None:
    with pytest.raises(
        MediaRequestRepositoryError,
        match="not found",
    ):
        repository.delete("missing-request")


def test_writes_use_shared_atomic_json_helper(
    repository: JsonMediaRequestRepository,
) -> None:
    request = make_request()
    repository.initialize()

    with patch(
        "atlas.media_requests.repository.write_json_atomic",
    ) as writer:
        repository.save(request)

    writer.assert_called_once()
    destination, payload = writer.call_args.args
    assert destination == repository.registry_file
    assert payload["requests"]["request-001"] == request.to_dict()


def test_invalid_json_is_reported_without_overwrite(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.initialize()
    repository.registry_file.write_text(
        "{invalid",
        encoding="utf-8",
    )

    with pytest.raises(
        MediaRequestRepositoryError,
        match="invalid JSON",
    ):
        repository.list()

    assert repository.registry_file.read_text(
        encoding="utf-8"
    ) == "{invalid"


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"schema_version": 999, "requests": {}},
        {"schema_version": SCHEMA_VERSION, "requests": []},
    ],
)
def test_invalid_registry_shape_is_rejected(
    repository: JsonMediaRequestRepository,
    payload: object,
) -> None:
    repository.initialize()
    repository.registry_file.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(MediaRequestRepositoryError):
        repository.list()


def test_invalid_record_shape_is_rejected(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.initialize()
    repository.registry_file.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "requests": {
                    "request-001": [],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        MediaRequestRepositoryError,
        match="record must be an object",
    ):
        repository.list()


def test_registry_key_mismatch_is_rejected(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.initialize()
    repository.registry_file.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "requests": {
                    "request-001": make_request(
                        request_id="request-002",
                    ).to_dict(),
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        MediaRequestRepositoryError,
        match="key does not match",
    ):
        repository.list()


def test_invalid_domain_record_is_rejected(
    repository: JsonMediaRequestRepository,
) -> None:
    payload = make_request().to_dict()
    payload["status"] = "unsupported"

    repository.initialize()
    repository.registry_file.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "requests": {
                    "request-001": payload,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        MediaRequestRepositoryError,
        match="invalid media-request record",
    ):
        repository.list()


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("terminal", True),
        ("active", False),
    ],
)
def test_inconsistent_derived_fields_are_rejected(
    repository: JsonMediaRequestRepository,
    field_name: str,
    value: bool,
) -> None:
    payload = make_request().to_dict()
    payload[field_name] = value

    repository.initialize()
    repository.registry_file.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "requests": {
                    "request-001": payload,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        MediaRequestRepositoryError,
        match="derived field does not match",
    ):
        repository.list()


def test_registry_requests_are_persisted_in_key_order(
    repository: JsonMediaRequestRepository,
) -> None:
    repository.save(
        make_request(
            request_id="request-z",
            provider_request_id="provider-z",
        )
    )
    repository.save(
        make_request(
            request_id="request-a",
            provider_request_id="provider-a",
        )
    )

    raw = repository.registry_file.read_text(encoding="utf-8")
    assert raw.index('"request-a"') < raw.index('"request-z"')

def test_enospc_is_normalized_and_preserves_registry(
    repository: JsonMediaRequestRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = make_request()
    repository.save(original)
    committed = repository.registry_file.read_text(encoding="utf-8")

    def fail_write(path: Path, value: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(
        "atlas.media_requests.repository.write_json_atomic",
        fail_write,
    )

    replacement = make_request(
        status="approved",
        updated_at="2026-08-02T20:30:00Z",
    )

    with pytest.raises(
        MediaRequestRepositoryError,
        match="unable to persist media-request registry",
    ) as captured:
        repository.replace(replacement)

    assert isinstance(captured.value.__cause__, OSError)
    assert captured.value.__cause__.errno == errno.ENOSPC
    assert repository.registry_file.read_text(encoding="utf-8") == committed
    assert repository.get(original.request_id) == original


def test_initialize_normalizes_enospc(
    repository: JsonMediaRequestRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write(path: Path, value: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(
        "atlas.media_requests.repository.write_json_atomic",
        fail_write,
    )

    with pytest.raises(
        MediaRequestRepositoryError,
        match="unable to persist media-request registry",
    ) as captured:
        repository.initialize()

    assert isinstance(captured.value.__cause__, OSError)
    assert captured.value.__cause__.errno == errno.ENOSPC
    assert repository.registry_file.exists() is False
