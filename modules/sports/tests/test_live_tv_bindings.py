from __future__ import annotations

import json
from pathlib import Path

import pytest

from live_tv_bindings import (
    LiveTvBindingError,
    LiveTvBindingRegistry,
)


def test_absent_state_fails_closed(
    tmp_path: Path,
) -> None:
    registry = LiveTvBindingRegistry(
        tmp_path / "bindings.json"
    )

    assert registry.list_bindings() == ()
    assert registry.resolve("sports-event-1") is None


def test_exact_round_trip(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"
    registry = LiveTvBindingRegistry(path)

    binding = registry.set(
        "sports-event-1",
        "jellyfin-1",
    )

    assert binding.safe_dict() == {
        "atlas_channel_id": "sports-event-1",
        "jellyfin_item_id": "jellyfin-1",
    }
    assert registry.resolve("sports-event-1") == "jellyfin-1"

    serialized = path.read_text(encoding="utf-8")
    assert "stream_url" not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized


def test_jellyfin_item_is_unique(
    tmp_path: Path,
) -> None:
    registry = LiveTvBindingRegistry(
        tmp_path / "bindings.json"
    )
    registry.set("sports-event-1", "jellyfin-1")

    with pytest.raises(
        LiveTvBindingError,
        match="already bound",
    ):
        registry.set(
            "sports-event-2",
            "jellyfin-1",
        )


def test_duplicate_json_keys_are_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"
    path.write_text(
        (
            '{"version":1,"bindings":{'
            '"a":{"jellyfin_item_id":"1"},'
            '"a":{"jellyfin_item_id":"2"}}}'
            "\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        LiveTvBindingError,
        match="duplicate JSON object key",
    ):
        LiveTvBindingRegistry(path).list_bindings()


def test_persisted_duplicate_jellyfin_ids_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "bindings": {
                    "a": {
                        "jellyfin_item_id": "same"
                    },
                    "b": {
                        "jellyfin_item_id": "same"
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        LiveTvBindingError,
        match="cannot bind to multiple",
    ):
        LiveTvBindingRegistry(path).list_bindings()


def test_delete_is_exact_and_idempotent(
    tmp_path: Path,
) -> None:
    registry = LiveTvBindingRegistry(
        tmp_path / "bindings.json"
    )
    registry.set("sports-event-1", "jellyfin-1")

    assert registry.delete("sports-event-1") is True
    assert registry.delete("sports-event-1") is False
    assert registry.resolve("sports-event-1") is None


def test_ensure_creates_versioned_empty_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"
    registry = LiveTvBindingRegistry(path)

    registry.ensure()

    assert json.loads(
        path.read_text(encoding="utf-8")
    ) == {
        "version": 1,
        "bindings": {},
    }
