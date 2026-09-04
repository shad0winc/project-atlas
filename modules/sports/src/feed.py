#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lifecycle import should_surface_game
from live_sources import (
    LiveSourceCatalog,
    LiveSourceCatalogError,
    load_live_source_catalog,
)

PREGAME_WINDOW_MINUTES = int(
    os.getenv(
        "SPORTS_PREGAME_WINDOW_MINUTES",
        "60",
    )
)

STATE_FILE = Path(
    os.getenv(
        "SPORTS_STATE_FILE",
        "/mnt/storage/configs/sportyfin/state/games.json",
    )
)

OUTPUT_DIR = Path(
    os.getenv(
        "SPORTS_OUTPUT_DIR",
        "/mnt/storage/configs/sportyfin/output",
    )
)

M3U_FILE = OUTPUT_DIR / "sports.m3u"
XMLTV_FILE = OUTPUT_DIR / "sports.xml"


def load_games() -> dict[str, dict[str, Any]]:
    if not STATE_FILE.exists():
        return {}

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def active_games(
    games: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if now is None:
        now = datetime.now(timezone.utc)

    return [
        game
        for game in games.values()
        if should_surface_game(
            game,
            now,
            PREGAME_WINDOW_MINUTES,
        )
    ]


def catalog_feed_games(
    games: list[dict[str, Any]],
    catalog: LiveSourceCatalog,
) -> list[dict[str, Any]]:
    """Return only feed entries backed by an authorized live source.

    Raw stream_url values supplied by metadata providers or state are never
    trusted here. Event playback requires an explicit provider/event mapping
    in the authorized live-source catalog.
    """

    feed_games: list[dict[str, Any]] = []

    for game in games:
        provider = str(game.get("provider") or "").strip().lower()
        provider_event_id = str(
            game.get("provider_event_id") or ""
        ).strip()

        if not provider or not provider_event_id:
            continue

        source = catalog.for_event(
            provider,
            provider_event_id,
        )

        if source is None:
            continue

        mapped = dict(game)
        mapped["stream_url"] = source.stream_url
        mapped["_atlas_live_source_id"] = source.source_id
        feed_games.append(mapped)

    for source in catalog.standalone_sources():
        feed_games.append(
            {
                "id": f"live-{source.source_id}",
                "name": source.name,
                "stream_url": source.stream_url,
                "_atlas_live_source_id": source.source_id,
                "_atlas_standalone_live_source": True,
            }
        )

    return feed_games


def game_name(game: dict[str, Any]) -> str:
    return str(
        game.get("name")
        or game.get("id")
        or "Unknown Sports Event"
    )


def stream_url(game: dict[str, Any]) -> str:
    return str(
        game.get("stream_url", "")
    ).strip()


def xmltv_timestamp(value: str | None) -> str:
    if value:
        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            return parsed.astimezone(timezone.utc).strftime(
                "%Y%m%d%H%M%S +0000"
            )
        except ValueError:
            pass

    return datetime.now(timezone.utc).strftime(
        "%Y%m%d%H%M%S +0000"
    )


def programme_stop(game: dict[str, Any]) -> str:
    start_value = game.get("start_at")

    if start_value:
        try:
            start = datetime.fromisoformat(
                str(start_value).replace("Z", "+00:00")
            )

            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)

            duration_minutes = int(
                game.get("duration_minutes", 240)
            )

            stop = start + timedelta(
                minutes=duration_minutes
            )

            return stop.astimezone(timezone.utc).strftime(
                "%Y%m%d%H%M%S +0000"
            )
        except (ValueError, TypeError):
            pass

    return (
        datetime.now(timezone.utc)
        + timedelta(hours=4)
    ).strftime("%Y%m%d%H%M%S +0000")


def render_m3u(
    games: list[dict[str, Any]],
) -> str:
    lines = ["#EXTM3U", ""]

    for game in games:
        url = stream_url(game)

        if not url:
            continue

        channel_id = f"sports-{game['id']}"
        name = game_name(game)

        lines.append(
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{name}" group-title="Sports",'
            f"{name}"
        )

        lines.append(url)
        lines.append("")

    return "\n".join(lines) + "\n"


def render_xmltv(
    games: list[dict[str, Any]],
) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="Project Atlas">',
    ]

    for game in games:
        channel_id = f"sports-{game['id']}"
        name = html.escape(game_name(game))

        lines.extend(
            [
                f'  <channel id="{channel_id}">',
                f"    <display-name>{name}</display-name>",
                "  </channel>",
            ]
        )

    for game in games:
        if bool(game.get("_atlas_standalone_live_source")):
            continue

        channel_id = f"sports-{game['id']}"
        name = html.escape(game_name(game))

        start = xmltv_timestamp(
            game.get("start_at")
        )

        stop = programme_stop(game)

        lines.extend(
            [
                (
                    f'  <programme start="{start}" '
                    f'stop="{stop}" '
                    f'channel="{channel_id}">'
                ),
                f"    <title>{name}</title>",
                "    <category>Sports</category>",
                "  </programme>",
            ]
        )

    lines.append("</tv>")

    return "\n".join(lines) + "\n"


def write_atomic(
    destination: Path,
    content: str,
) -> None:
    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    temporary.write_text(
        content,
        encoding="utf-8",
    )

    temporary.replace(destination)


def generate_feed() -> int:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    active = active_games(
        load_games()
    )

    try:
        catalog = load_live_source_catalog()
    except LiveSourceCatalogError:
        write_atomic(
            M3U_FILE,
            render_m3u([]),
        )
        write_atomic(
            XMLTV_FILE,
            render_xmltv([]),
        )
        raise

    games = catalog_feed_games(
        active,
        catalog,
    )

    write_atomic(
        M3U_FILE,
        render_m3u(games),
    )

    write_atomic(
        XMLTV_FILE,
        render_xmltv(games),
    )

    print(
        f"Sports feed generated: "
        f"{len(active)} active game(s), "
        f"{len(games)} authorized live channel(s)"
    )

    return 0


def main() -> int:
    try:
        return generate_feed()
    except (
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"Sports feed generation failed: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
