"""Shared Jellyfin MediaBrowser authorization construction."""

from __future__ import annotations


DEFAULT_JELLYFIN_CLIENT_NAME = "Project Atlas"
DEFAULT_JELLYFIN_CLIENT_VERSION = "0.1.0"
DEFAULT_JELLYFIN_DEVICE_NAME = "Atlas API"
DEFAULT_JELLYFIN_DEVICE_ID = "atlas-api"


def build_jellyfin_authorization(
    *,
    token: str | None = None,
    client_name: str = DEFAULT_JELLYFIN_CLIENT_NAME,
    client_version: str = DEFAULT_JELLYFIN_CLIENT_VERSION,
    device_name: str = DEFAULT_JELLYFIN_DEVICE_NAME,
    device_id: str = DEFAULT_JELLYFIN_DEVICE_ID,
) -> str:
    """Build one Jellyfin MediaBrowser Authorization header value."""

    authorization = (
        f'MediaBrowser Client="{client_name}", '
        f'Device="{device_name}", '
        f'DeviceId="{device_id}", '
        f'Version="{client_version}"'
    )

    if token is None:
        return authorization

    normalized_token = token.strip()
    if not normalized_token:
        raise ValueError("Jellyfin token cannot be empty.")

    return (
        f'{authorization}, '
        f'Token="{normalized_token}"'
    )
