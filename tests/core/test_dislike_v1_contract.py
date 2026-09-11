"""RED contracts for the Atlas v1 Dislike / 24-hour cleanup action.

These tests intentionally describe the minimum architecture required by the
v1 Theater / Watch Actions contract.  They are structural first: production
implementation is added only after the RED contract is reviewed.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    path = ROOT / relative

    assert path.is_file(), (
        f"required v1 Dislike surface is missing: {relative}"
    )

    return path.read_text(
        encoding="utf-8",
    )


def test_user_scoped_dislike_state_domain_exists() -> None:
    """Dislike needs durable user/media identity analogous to Favorites."""

    source = _read(
        "atlas/dislikes.py"
    )

    assert "DislikeStore" in source

    for required_identity in (
        "user_id",
        "provider",
        "item_id",
    ):
        assert required_identity in source


def test_dislike_mutation_service_exists() -> None:
    """Preference mutation owns validation plus lifecycle events."""

    source = _read(
        "atlas/dislike_service.py"
    )

    assert "DislikeService" in source
    assert "dislike.created" in source
    assert "dislike.removed" in source


def test_authenticated_dislike_api_surface_exists() -> None:
    """The public API must expose an authenticated self-scoped boundary."""

    route_source = _read(
        "apps/api/atlas_api/routes/v1/dislikes.py"
    )

    router_source = _read(
        "apps/api/atlas_api/routes/v1/__init__.py"
    )

    assert 'prefix="/dislikes"' in route_source

    # A caller must not choose another Atlas owner.
    assert "current_user" in route_source
    assert "user_id" in route_source

    assert "dislikes_router" in router_source


def test_dislike_has_24_hour_accelerated_retention_contract() -> None:
    """Dislike must become cleanup-eligible after 24 hours."""

    source = _read(
        "atlas/retention/service.py"
    ).lower()

    assert "dislike" in source

    accepted_contracts = (
        "timedelta(hours=24)",
        "timedelta(hours = 24)",
        "dislike_retention_hours = 24",
        "dislike_cleanup_hours = 24",
        "dislike_delete_hours = 24",
    )

    assert any(
        contract in source
        for contract in accepted_contracts
    ), (
        "retention must contain an explicit 24-hour "
        "Dislike cleanup contract"
    )


def test_library_exposes_dislike_action() -> None:
    """Library media must expose the v1 user-facing Dislike action."""

    source = _read(
        "apps/portal/features/media/components/"
        "MediaCatalogView.tsx"
    ).lower()

    assert "dislike" in source


def test_theater_exposes_dislike_action() -> None:
    """Atlas Theater must expose the same v1 Dislike action."""

    source = _read(
        "apps/portal/features/playback/components/"
        "AtlasTheaterPlayer.tsx"
    ).lower()

    assert "dislike" in source
