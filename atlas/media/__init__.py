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
from atlas.media.library_detail import (
    MEDIA_LIBRARY_IDS,
    MediaLibraryDetail,
    MediaLibraryDetailStatus,
    MediaLibraryFilesystem,
    MediaLibraryProvider,
    MediaLibrarySynchronization,
    MediaLibraryValidation,
)
from atlas.media.library_summary import (
    MediaLibraryCount,
    MediaLibraryStatus,
    MediaLibrarySummary,
)
from atlas.media.mutations import (
    MediaMutationDispatcher,
    MediaMutationDispatchError,
    MediaMutationMode,
)
from atlas.media.playback import (
    PlaybackAction,
    PlaybackActionKind,
    PlaybackSourceType,
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
    "PlaybackAction",
    "PlaybackActionKind",
    "PlaybackSourceType",
    "MEDIA_LIBRARY_IDS",
    "MediaLibraryDetail",
    "MediaLibraryDetailStatus",
    "MediaLibraryFilesystem",
    "MediaLibraryProvider",
    "MediaLibrarySynchronization",
    "MediaLibraryValidation",
    "MediaItem",
    "MediaLibraryCount",
    "MediaLibraryStatus",
    "MediaLibrarySummary",
    "MediaMutationDispatcher",
    "MediaMutationDispatchError",
    "MediaMutationMode",
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
