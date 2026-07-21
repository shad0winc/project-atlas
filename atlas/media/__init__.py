"""Provider-neutral media integration package for Project Atlas."""

from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
    ProviderCapabilityError,
)
from atlas.media.jellyfin import (
    JellyfinProvider,
    default_jellyfin_provider,
)
from atlas.media.provider import (
    MediaItem,
    MediaProvider,
    MediaProviderError,
    ProviderMutationError,
    ProviderMutationResult,
    ProviderOperation,
)
from atlas.media.recording import (
    RecordingMediaProvider,
)

__all__ = [
    "JellyfinProvider",
    "MediaItem",
    "MediaProvider",
    "MediaProviderError",
    "ProviderCapabilities",
    "ProviderCapability",
    "ProviderCapabilityError",
    "ProviderMutationError",
    "ProviderMutationResult",
    "ProviderOperation",
    "RecordingMediaProvider",
    "default_jellyfin_provider",
]
