"""Public standalone Sports channel discovery; no provider or playback calls."""
from __future__ import annotations
from collections.abc import Mapping, Sequence


def discover_live_channels(
    sources: Sequence[Mapping[str, object]],
    bindings: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    bound: set[str] = set()
    for binding in bindings:
        channel = binding.get("atlas_channel_id")
        item = binding.get("jellyfin_item_id")
        if not isinstance(channel, str) or not channel.strip():
            raise ValueError("Invalid live channel binding")
        if not isinstance(item, str) or not item.strip() or channel in bound:
            raise ValueError("Invalid or duplicate live channel binding")
        bound.add(channel)

    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for source in sources:
        if source.get("standalone") is not True:
            continue
        identity = source.get("id")
        channel = source.get("atlas_channel_id")
        name = source.get("name")
        if not all(isinstance(value, str) and value.strip() for value in (identity, channel, name)):
            raise ValueError("Incomplete standalone channel identity")
        if channel != f"sports-live-{identity}" or channel in seen:
            raise ValueError("Invalid or duplicate standalone channel identity")
        if source.get("provider") is not None or source.get("provider_event_id") is not None:
            raise ValueError("Standalone channel must not impersonate a scheduled event")
        seen.add(channel)
        result.append({"atlas_channel_id": channel, "name": name, "playback_configured": channel in bound})
    return sorted(result, key=lambda row: (str(row["name"]).casefold(), str(row["atlas_channel_id"])))
