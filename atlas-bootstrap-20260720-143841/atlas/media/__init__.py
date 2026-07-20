"""Media provider framework for Project Atlas."""
from atlas.media.jellyfin import JellyfinProvider, default_jellyfin_provider
from atlas.media.provider import MediaItem, MediaProvider, MediaProviderError
__all__ = ["JellyfinProvider", "MediaItem", "MediaProvider", "MediaProviderError", "default_jellyfin_provider"]
