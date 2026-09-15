from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SPORTS_SRC = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "sports"
    / "src"
)

if str(SPORTS_SRC) not in sys.path:
    sys.path.insert(0, str(SPORTS_SRC))

import private_api  # noqa: E402


class _Catalog:
    def for_event(
        self,
        provider: str,
        provider_event_id: str,
    ):
        assert provider == "thesportsdb"
        assert provider_event_id == "finished-event"

        return SimpleNamespace(
            atlas_channel_id=(
                "sports-live-thesportsdb-finished-event"
            )
        )


class _Bindings:
    def resolve(
        self,
        atlas_channel_id: str,
    ) -> str | None:
        assert (
            atlas_channel_id
            == "sports-live-thesportsdb-finished-event"
        )

        return "jellyfin-live-tv-item"


def test_finished_event_is_unavailable_even_with_stale_source_and_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Terminal Sports events must not advertise Watch Live merely because
    stale source and Jellyfin binding state still exists.
    """

    monkeypatch.setattr(
        private_api,
        "load_live_source_catalog",
        lambda: _Catalog(),
    )

    monkeypatch.setattr(
        private_api,
        "default_live_tv_binding_registry",
        lambda: _Bindings(),
    )

    # The corrective implementation is expected to consult the existing
    # authoritative games state. raising=False intentionally keeps this
    # regression RED against today's implementation without inventing a
    # production interface that does not yet exist.
    monkeypatch.setattr(
        private_api,
        "load_games",
        lambda: {
            "thesportsdb-finished-event": {
                "id": "thesportsdb-finished-event",
                "provider": "thesportsdb",
                "provider_event_id": "finished-event",
                "status": "final",
                "lifecycle_state": "finished",
            }
        },
        raising=False,
    )

    assert private_api._live_availability(
        "thesportsdb",
        "finished-event",
    ) == {
        "available": False,
        "atlas_channel_id": None,
    }
