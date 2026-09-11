from __future__ import annotations

import hashlib


ATLAS_JELLYFIN_CHANNEL_NUMBER_BASE = 900_000_000
ATLAS_JELLYFIN_CHANNEL_NUMBER_SLOTS = 100_000_000


def atlas_jellyfin_channel_number(
    atlas_channel_id: str,
) -> str:
    """Return the stable reserved Jellyfin number for an Atlas channel."""

    normalized = str(
        atlas_channel_id
    ).strip()

    if not normalized:
        raise ValueError(
            "atlas_channel_id is required"
        )

    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).digest()

    slot = (
        int.from_bytes(
            digest[:8],
            byteorder="big",
            signed=False,
        )
        % ATLAS_JELLYFIN_CHANNEL_NUMBER_SLOTS
    )

    return str(
        ATLAS_JELLYFIN_CHANNEL_NUMBER_BASE
        + slot
    )
