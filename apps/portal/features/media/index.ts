export { loadMediaDiscovery, loadMediaSearch } from "./api/discovery";
export type { ReadMediaDiscoveryOptions, SearchMediaDiscoveryOptions } from "./api/discovery";

export { loadMedia } from "./api/media";
export type { LoadMediaOptions } from "./api/media";

export { MediaDiscoveryContent, MediaDiscoveryView } from "./components/MediaDiscoveryView";

export type {
  MediaDiscoveryRequestAction,
  MediaDiscoveryRequestActions,
  MediaDiscoverySeriesState,
  MediaDiscoverySeriesStates
} from "./components/MediaDiscoveryView";
export { MediaError } from "./components/MediaError";
export { MediaLibraryCard } from "./components/MediaLibraryCard";
export { MediaLibraryGrid } from "./components/MediaLibraryGrid";
export { MediaOverview } from "./components/MediaOverview";
export { MediaRefreshButton } from "./components/MediaRefreshButton";
export { MediaSkeleton } from "./components/MediaSkeleton";
export { MediaSummary } from "./components/MediaSummary";
export { MediaView } from "./components/MediaView";

export { useMediaDiscovery } from "./hooks/use-media-discovery";
export type {
  MediaDiscoveryErrorState,
  MediaDiscoveryLoadingState,
  MediaDiscoveryMode,
  MediaDiscoveryReadyState,
  MediaDiscoveryState,
  UseMediaDiscoveryResult
} from "./hooks/use-media-discovery";

export { useMedia } from "./hooks/use-media";
export type { UseMediaResult } from "./hooks/use-media";

export { readMediaDiscovery, searchMediaDiscovery } from "./services/discovery";

export { readMediaSeriesDetail } from "./services/series";
export type { ReadMediaSeriesDetailOptions } from "./services/series";

export {
  MEDIA_SERIES_STATUSES,
  createMediaSeriesDetail,
  createMediaSeriesSeason,
  mediaSeriesRequestType
} from "./types/series";

export type {
  MediaSeriesDetail,
  MediaSeriesRequestType,
  MediaSeriesSeason,
  MediaSeriesStatus
} from "./types/series";
export { readMediaSnapshot } from "./services/media";
export type { ReadMediaSnapshotOptions } from "./services/media";

export { createMediaLibrary, createMediaSnapshot, summarizeMediaSnapshot } from "./types/media";

export type {
  MediaLibrary,
  MediaLibraryStatus,
  MediaSnapshot,
  MediaSummary as MediaSummaryModel
} from "./types/media";

export { createMediaState } from "./types/media-state";
export type {
  MediaErrorState,
  MediaLoadingState,
  MediaReadyState,
  MediaState
} from "./types/media-state";

export {
  MEDIA_DISCOVERY_AVAILABILITIES,
  MEDIA_DISCOVERY_MEDIA_TYPES,
  createMediaDiscoveryItem,
  createMediaDiscoveryPage,
  mediaDiscoveryAvailabilityLabel,
  normalizeMediaDiscoveryAvailability,
  normalizeMediaDiscoveryPageNumber,
  normalizeMediaDiscoveryProviderId,
  normalizeMediaDiscoveryQuery,
  normalizeMediaDiscoveryType
} from "./types/discovery";

export type {
  CreateMediaDiscoveryPageInput,
  MediaDiscoveryAvailability,
  MediaDiscoveryItem,
  MediaDiscoveryMediaType,
  MediaDiscoveryPage
} from "./types/discovery";
