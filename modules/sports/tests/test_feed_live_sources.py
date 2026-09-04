from __future__ import annotations

import pytest

import feed
from live_sources import (
    LiveSource,
    LiveSourceCatalog,
    LiveSourceCatalogError,
)
from feed import (
    catalog_feed_games,
    render_m3u,
    render_xmltv,
)


def event_game(
    *,
    provider: str = "thesportsdb",
    provider_event_id: str = "event-1",
) -> dict[str, object]:
    return {
        "id": "game-1",
        "provider": provider,
        "provider_event_id": provider_event_id,
        "name": "Atlas United vs Atlas City",
        "start_at": "2026-09-04T00:00:00Z",
        "duration_minutes": 180,
        "stream_url": "https://untrusted.invalid/provider.m3u8",
    }


def test_no_catalog_means_no_playable_feed_entries() -> None:
    games = catalog_feed_games(
        [event_game()],
        LiveSourceCatalog(()),
    )

    assert games == []
    assert render_m3u(games) == "#EXTM3U\n\n"
    assert "<channel " not in render_xmltv(games)
    assert "<programme " not in render_xmltv(games)


def test_event_stream_requires_explicit_catalog_mapping() -> None:
    catalog = LiveSourceCatalog(
        (
            LiveSource(
                source_id="authorized-game",
                name="Authorized Game Feed",
                stream_url=(
                    "https://authorized.invalid/game.m3u8"
                ),
                provider="thesportsdb",
                provider_event_id="event-1",
            ),
        )
    )

    games = catalog_feed_games(
        [event_game()],
        catalog,
    )

    assert len(games) == 1
    assert games[0]["stream_url"] == (
        "https://authorized.invalid/game.m3u8"
    )
    assert "untrusted.invalid" not in render_m3u(games)
    assert "authorized.invalid" in render_m3u(games)


def test_mismatched_event_mapping_is_not_used() -> None:
    catalog = LiveSourceCatalog(
        (
            LiveSource(
                source_id="other-game",
                name="Other Game Feed",
                stream_url=(
                    "https://authorized.invalid/other.m3u8"
                ),
                provider="thesportsdb",
                provider_event_id="event-2",
            ),
        )
    )

    assert catalog_feed_games(
        [event_game()],
        catalog,
    ) == []


def test_standalone_channel_is_in_m3u_and_xmltv_channel_list() -> None:
    catalog = LiveSourceCatalog(
        (
            LiveSource(
                source_id="redzone",
                name="NFL RedZone",
                stream_url=(
                    "https://authorized.invalid/redzone.m3u8"
                ),
                standalone=True,
            ),
        )
    )

    games = catalog_feed_games([], catalog)
    m3u = render_m3u(games)
    xmltv = render_xmltv(games)

    assert len(games) == 1
    assert "NFL RedZone" in m3u
    assert "https://authorized.invalid/redzone.m3u8" in m3u
    assert 'tvg-id="sports-live-redzone"' in m3u
    assert '<channel id="sports-live-redzone">' in xmltv
    assert "NFL RedZone" in xmltv
    assert "<programme " not in xmltv


def test_event_channel_retains_real_programme_metadata() -> None:
    catalog = LiveSourceCatalog(
        (
            LiveSource(
                source_id="authorized-game",
                name="Authorized Game Feed",
                stream_url=(
                    "https://authorized.invalid/game.m3u8"
                ),
                provider="thesportsdb",
                provider_event_id="event-1",
            ),
        )
    )

    games = catalog_feed_games(
        [event_game()],
        catalog,
    )
    xmltv = render_xmltv(games)

    assert '<channel id="sports-game-1">' in xmltv
    assert '<programme start="20260904000000 +0000"' in xmltv
    assert 'stop="20260904030000 +0000"' in xmltv
    assert 'channel="sports-game-1">' in xmltv
    assert "Atlas United vs Atlas City" in xmltv


def test_invalid_configured_catalog_clears_stale_feed_and_reraises(
    tmp_path,
    monkeypatch,
) -> None:
    m3u_file = tmp_path / "sports.m3u"
    xmltv_file = tmp_path / "sports.xml"
    catalog_file = tmp_path / "live-sources.json"

    stale_url = "https://stale.invalid/authorized-before-error.m3u8"

    m3u_file.write_text(
        (
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="sports-old",Old Authorized Feed\n'
            f'{stale_url}\n'
        ),
        encoding="utf-8",
    )
    xmltv_file.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<tv generator-info-name="Project Atlas">\n'
            '  <channel id="sports-old">\n'
            '    <display-name>Old Authorized Feed</display-name>\n'
            '  </channel>\n'
            '</tv>\n'
        ),
        encoding="utf-8",
    )
    catalog_file.write_text(
        "{ malformed json",
        encoding="utf-8",
    )

    monkeypatch.setattr(feed, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(feed, "M3U_FILE", m3u_file)
    monkeypatch.setattr(feed, "XMLTV_FILE", xmltv_file)
    monkeypatch.setattr(feed, "load_games", lambda: {})
    monkeypatch.setenv(
        "SPORTS_LIVE_SOURCE_CATALOG_PATH",
        str(catalog_file),
    )

    with pytest.raises(LiveSourceCatalogError):
        feed.generate_feed()

    assert m3u_file.read_text(encoding="utf-8") == "#EXTM3U\n\n"

    xmltv = xmltv_file.read_text(encoding="utf-8")
    assert xmltv == feed.render_xmltv([])
    assert "<channel " not in xmltv
    assert "<programme " not in xmltv

    assert stale_url not in m3u_file.read_text(encoding="utf-8")
    assert "sports-old" not in xmltv
