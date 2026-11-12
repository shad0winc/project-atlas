import type { PlaybackActionKind, PlaybackSourceType } from "./playback";

export type PlaybackTrack = Readonly<{
  index: number;
  kind: "audio" | "subtitle";
  label: string;
  language?: string;
  codec?: string;
  default: boolean;
  forced: boolean;
}>;

export type PlaybackVersion = Readonly<{
  id: string;
  width: number;
  height: number;
}>;

export type PlaybackSession = Readonly<{
  available: boolean;
  action: PlaybackActionKind;
  label: string;
  backend: string;
  sourceType: PlaybackSourceType;
  provider: string;
  requestedTargetId: string;
  playableTargetId: string;
  title: string;
  overview?: string;
  cast?: readonly string[];
  directors?: readonly string[];
  producers?: readonly string[];
  productionLocations?: readonly string[];
  videoWidth?: number;
  videoHeight?: number;
  versions?: readonly PlaybackVersion[];
  selectedVersionId?: string;
  mediaType: string;
  durationTicks?: number;
  canSeek: boolean;
  playbackBootstrapUrl: string;
  playbackCapability: string;
  audioTracks: readonly PlaybackTrack[];
  subtitleTracks: readonly PlaybackTrack[];
  previousTargetId?: string;
  nextTargetId?: string;
  seriesId?: string;
  seriesTmdbId?: string;
}>;
