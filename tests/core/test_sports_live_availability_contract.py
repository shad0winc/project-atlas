from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_writer_packages_live_source_reader_narrowly() -> None:
    dockerfile = (
        ROOT / "modules" / "sports" / "Dockerfile.private-api"
    ).read_text(encoding="utf-8")

    assert (
        "COPY modules/sports/src/live_sources.py /srv/sports/live_sources.py"
        in dockerfile
    )
    assert "COPY modules/sports/src/*.py" not in dockerfile


def test_writer_has_read_only_live_source_config_mount() -> None:
    compose = (ROOT / "stack" / "ingress.yml").read_text(encoding="utf-8")
    start = compose.index("\n  sports-writer:\n")
    end = compose.index("\n  identity-writer:\n", start)
    writer = compose[start:end]

    assert (
        'SPORTS_LIVE_SOURCE_CATALOG_PATH: '
        '"${SPORTS_LIVE_SOURCE_CATALOG_PATH:-}"'
        in writer
    )
    assert (
        "/mnt/storage/configs/sportyfin/config:"
        "/mnt/storage/configs/sportyfin/config:ro"
        in writer
    )
    assert (
        "/mnt/storage/configs/sportyfin/config:"
        "/mnt/storage/configs/sportyfin/config:rw"
        not in writer
    )


def test_public_live_availability_never_exposes_private_media_identity() -> None:
    route = (
        ROOT
        / "apps"
        / "api"
        / "atlas_api"
        / "routes"
        / "v1"
        / "sports_playback.py"
    ).read_text(encoding="utf-8")

    start = route.index('    "/availability",')
    end = route.index('    "/{atlas_channel_id}/session",', start)
    availability = route[start:end].lower()

    for forbidden in (
        "jellyfin_item_id",
        "stream_url",
        "stream_path",
        "playback_capability",
        "access_token",
        "authorization",
    ):
        assert forbidden not in availability


def test_live_feed_and_availability_share_source_owned_channel_identity() -> None:
    live_sources = (
        ROOT / "modules" / "sports" / "src" / "live_sources.py"
    ).read_text(encoding="utf-8")
    feed = (
        ROOT / "modules" / "sports" / "src" / "feed.py"
    ).read_text(encoding="utf-8")
    private_api = (
        ROOT / "modules" / "sports" / "src" / "private_api.py"
    ).read_text(encoding="utf-8")

    assert 'return f"sports-live-{self.source_id}"' in live_sources
    assert 'mapped["_atlas_channel_id"] = source.atlas_channel_id' in feed
    assert '"_atlas_channel_id": source.atlas_channel_id' in feed
    assert "atlas_channel_id = source.atlas_channel_id" in private_api
