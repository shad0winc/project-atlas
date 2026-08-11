"""Runtime configuration contracts for explicit media-request routing."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_ingress_passes_tv_routing_without_hard_coded_ids() -> None:
    content = (
        ROOT
        / "stack"
        / "ingress.yml"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        'ATLAS_JELLYSEERR_TV_SERVER_ID: '
        '"${ATLAS_JELLYSEERR_TV_SERVER_ID:-}"'
        in content
    )
    assert (
        'ATLAS_JELLYSEERR_ANIME_TV_SERVER_ID: '
        '"${ATLAS_JELLYSEERR_ANIME_TV_SERVER_ID:-}"'
        in content
    )

    assert (
        'ATLAS_JELLYSEERR_TV_SERVER_ID: "0"'
        not in content
    )
    assert (
        'ATLAS_JELLYSEERR_ANIME_TV_SERVER_ID: "1"'
        not in content
    )


def test_environment_example_declares_explicit_tv_routes() -> None:
    content = (
        ROOT
        / ".env.example"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "ATLAS_JELLYSEERR_TV_SERVER_ID="
        in content
    )
    assert (
        "ATLAS_JELLYSEERR_ANIME_TV_SERVER_ID="
        in content
    )
    assert "Server ID 0 is valid." in content
