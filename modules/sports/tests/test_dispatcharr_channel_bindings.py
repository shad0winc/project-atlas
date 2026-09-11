from __future__ import annotations

import json
from pathlib import Path

import pytest

from dispatcharr_channel_bindings import (
    DispatcharrChannelBindingError,
    DispatcharrChannelBindingRegistry,
)


def test_absent_state_resolves_to_none(
    tmp_path: Path,
) -> None:
    registry = (
        DispatcharrChannelBindingRegistry(
            tmp_path / "bindings.json"
        )
    )

    assert registry.list_bindings() == ()
    assert (
        registry.resolve(
            "sports-live-event-1"
        )
        is None
    )


def test_exact_round_trip_and_safe_mapping(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    registry = (
        DispatcharrChannelBindingRegistry(
            path
        )
    )

    binding = registry.set(
        "sports-live-event-1",
        42,
        (
            "00000000-0000-0000-0000-"
            "000000000042"
        ),
    )

    assert binding.safe_dict() == {
        "atlas_channel_id": (
            "sports-live-event-1"
        ),
        "dispatcharr_channel_id": 42,
        "dispatcharr_channel_uuid": (
            "00000000-0000-0000-0000-"
            "000000000042"
        ),
    }

    assert registry.resolve(
        "sports-live-event-1"
    ) == binding

    rendered = path.read_text(
        encoding="utf-8"
    ).casefold()

    for forbidden in (
        "stream_url",
        "http://",
        "https://",
        "password",
        "username",
        "token",
        "backend_reference",
    ):
        assert forbidden not in rendered


def test_ensure_creates_versioned_empty_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    registry = (
        DispatcharrChannelBindingRegistry(
            path
        )
    )

    registry.ensure()

    assert json.loads(
        path.read_text(
            encoding="utf-8"
        )
    ) == {
        "version": 1,
        "bindings": {},
    }


def test_channel_id_is_unique(
    tmp_path: Path,
) -> None:
    registry = (
        DispatcharrChannelBindingRegistry(
            tmp_path / "bindings.json"
        )
    )

    registry.set(
        "sports-live-event-1",
        42,
        "uuid-42",
    )

    with pytest.raises(
        DispatcharrChannelBindingError,
        match="ID is already bound",
    ):
        registry.set(
            "sports-live-event-2",
            42,
            "uuid-other",
        )


def test_channel_uuid_is_unique(
    tmp_path: Path,
) -> None:
    registry = (
        DispatcharrChannelBindingRegistry(
            tmp_path / "bindings.json"
        )
    )

    registry.set(
        "sports-live-event-1",
        42,
        "uuid-42",
    )

    with pytest.raises(
        DispatcharrChannelBindingError,
        match="UUID is already bound",
    ):
        registry.set(
            "sports-live-event-2",
            43,
            "uuid-42",
        )


def test_same_atlas_channel_can_be_reconciled(
    tmp_path: Path,
) -> None:
    registry = (
        DispatcharrChannelBindingRegistry(
            tmp_path / "bindings.json"
        )
    )

    registry.set(
        "sports-live-event-1",
        42,
        "uuid-42",
    )

    replacement = registry.set(
        "sports-live-event-1",
        43,
        "uuid-43",
    )

    assert replacement.dispatcharr_channel_id == 43
    assert replacement.dispatcharr_channel_uuid == "uuid-43"


def test_persisted_duplicate_channel_id_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "bindings": {
                    "a": {
                        "dispatcharr_channel_id": 42,
                        "dispatcharr_channel_uuid": "uuid-a",
                    },
                    "b": {
                        "dispatcharr_channel_id": 42,
                        "dispatcharr_channel_uuid": "uuid-b",
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        DispatcharrChannelBindingError,
        match="cannot bind to multiple",
    ):
        (
            DispatcharrChannelBindingRegistry(
                path
            ).list_bindings()
        )


def test_persisted_duplicate_channel_uuid_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "bindings": {
                    "a": {
                        "dispatcharr_channel_id": 42,
                        "dispatcharr_channel_uuid": "same",
                    },
                    "b": {
                        "dispatcharr_channel_id": 43,
                        "dispatcharr_channel_uuid": "same",
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        DispatcharrChannelBindingError,
        match="cannot bind to multiple",
    ):
        (
            DispatcharrChannelBindingRegistry(
                path
            ).list_bindings()
        )


def test_duplicate_json_keys_are_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    path.write_text(
        (
            '{"version":1,"bindings":{'
            '"a":{"dispatcharr_channel_id":42,'
            '"dispatcharr_channel_uuid":"one"},'
            '"a":{"dispatcharr_channel_id":43,'
            '"dispatcharr_channel_uuid":"two"}}}'
            "\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        DispatcharrChannelBindingError,
        match="duplicate JSON object key",
    ):
        (
            DispatcharrChannelBindingRegistry(
                path
            ).list_bindings()
        )


@pytest.mark.parametrize(
    "channel_id",
    (
        0,
        -1,
        True,
        "42",
    ),
)
def test_invalid_channel_identifier_rejected(
    tmp_path: Path,
    channel_id,
) -> None:
    registry = (
        DispatcharrChannelBindingRegistry(
            tmp_path / "bindings.json"
        )
    )

    with pytest.raises(
        DispatcharrChannelBindingError
    ):
        registry.set(
            "sports-live-event-1",
            channel_id,
            "uuid-42",
        )


def test_delete_is_exact_and_idempotent(
    tmp_path: Path,
) -> None:
    registry = (
        DispatcharrChannelBindingRegistry(
            tmp_path / "bindings.json"
        )
    )

    registry.set(
        "sports-live-event-1",
        42,
        "uuid-42",
    )

    assert (
        registry.delete(
            "sports-live-event-1"
        )
        is True
    )

    assert (
        registry.delete(
            "sports-live-event-1"
        )
        is False
    )

    assert (
        registry.resolve(
            "sports-live-event-1"
        )
        is None
    )


def test_state_and_lock_symlinks_fail_closed(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real.json"
    real.write_text(
        '{"version":1,"bindings":{}}\n',
        encoding="utf-8",
    )

    state_link = tmp_path / "state.json"
    state_link.symlink_to(real)

    with pytest.raises(
        DispatcharrChannelBindingError,
        match="must not be a symlink",
    ):
        (
            DispatcharrChannelBindingRegistry(
                state_link
            ).list_bindings()
        )

    registry = (
        DispatcharrChannelBindingRegistry(
            tmp_path / "other.json"
        )
    )

    registry.lock_path.symlink_to(real)

    with pytest.raises(
        DispatcharrChannelBindingError,
        match="lock must not be a symlink",
    ):
        registry.ensure()
