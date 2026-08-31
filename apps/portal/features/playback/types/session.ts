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
  mediaType: string;
  durationTicks?: number;
  canSeek: boolean;
  playbackBootstrapUrl: string;
  playbackCapability: string;
  audioTracks: readonly PlaybackTrack[];
  subtitleTracks: readonly PlaybackTrack[];
  previousTargetId?: string;
  nextTargetId?: string;
}>;
