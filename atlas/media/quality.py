"""Conservative source-video dimensions; no filenames or provider secrets."""
from typing import Any


def video_dimensions(item: dict[str, Any]) -> dict[str, int]:
    streams = item.get("MediaStreams")
    if not isinstance(streams, list):
        return {}
    for stream in streams:
        if not isinstance(stream, dict) or str(stream.get("Type", "")).lower() != "video":
            continue
        if stream.get("IsExternal") or stream.get("IsAttachedPic"):
            continue
        if str(stream.get("Codec", "")).lower() in {"mjpeg", "jpeg", "png"}:
            continue
        width, height = stream.get("Width"), stream.get("Height")
        if all(isinstance(x, int) and not isinstance(x, bool) and 0 < x <= 32768
               for x in (width, height)):
            return {"video_width": width, "video_height": height}
    return {}
