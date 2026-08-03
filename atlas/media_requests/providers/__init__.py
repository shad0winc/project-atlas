"""Concrete media-request provider implementations.

Provider-independent contracts remain in :mod:`atlas.media_requests.provider`.
Shared HTTP behavior and concrete external adapters are exported here.
"""

from .base import (
    BaseMediaRequestHTTPProvider,
    MediaRequestHTTPError,
)
from .jellyseerr import (
    JellyseerrMediaRequestProvider,
    default_jellyseerr_media_request_provider,
)

__all__ = [
    "BaseMediaRequestHTTPProvider",
    "JellyseerrMediaRequestProvider",
    "MediaRequestHTTPError",
    "default_jellyseerr_media_request_provider",
]
