import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";
import type { PlaybackSession, PlaybackTrack } from "../types/session";

type PlaybackTrackTransport = Readonly<{
  index: number;
  kind: "audio" | "subtitle";
  label: string;
  language: string | null;
  codec: string | null;
  default: boolean;
  forced: boolean;
}>;

type PlaybackSessionTransport = Readonly<{
  available: boolean;
  action: "watch_now" | "watch_live" | "watch_recording";
  label: string;
  backend: string;
  source_type: "library" | "live" | "recording";
  provider: string;
  requested_target_id: string;
  playable_target_id: string;
  title: string;
  media_type: string;
  duration_ticks: number | null;
  can_seek: boolean;
  playback_bootstrap_url: string;
  playback_capability: string;
  audio_tracks: readonly PlaybackTrackTransport[];
  subtitle_tracks: readonly PlaybackTrackTransport[];
  previous_target_id: string | null;
  next_target_id: string | null;
}>;

function mapTrack(track: PlaybackTrackTransport): PlaybackTrack {
  return Object.freeze({
    index: track.index,
    kind: track.kind,
    label: track.label,
    ...(track.language === null ? {} : { language: track.language }),
    ...(track.codec === null ? {} : { codec: track.codec }),
    default: track.default,
    forced: track.forced
  });
}

export type SubtitleSelection = "auto" | "off" | number;

export async function resolvePlaybackSession(
  provider: string,
  itemId: string,
  signal?: AbortSignal,
  subtitle: SubtitleSelection = "auto"
): Promise<PlaybackSession> {
  const normalizedProvider = provider.trim().toLowerCase();
  const normalizedItemId = itemId.trim();
  if (!normalizedProvider || !normalizedItemId) {
    throw new Error("Playback identity is incomplete.");
  }

  const subtitleValue =
    typeof subtitle === "number" ? String(subtitle) : subtitle;

  const query = new URLSearchParams();

  if (subtitleValue !== "auto") {
    query.set("subtitle", subtitleValue);
  }

  const suffix = query.size === 0 ? "" : `?${query.toString()}`;

  const response = await authenticatedAtlasApiRequest<PlaybackSessionTransport>(
    `/media/playback/${encodeURIComponent(normalizedProvider)}/${encodeURIComponent(normalizedItemId)}/session${suffix}`,
    { method: "GET", cache: "no-store", signal }
  );

  if (
    response.provider !== normalizedProvider ||
    response.requested_target_id !== normalizedItemId
  ) {
    throw new Error(
      "Playback response did not match the requested media identity."
    );
  }

  return Object.freeze({
    available: response.available,
    action: response.action,
    label: response.label,
    backend: response.backend,
    sourceType: response.source_type,
    provider: response.provider,
    requestedTargetId: response.requested_target_id,
    playableTargetId: response.playable_target_id,
    title: response.title,
    mediaType: response.media_type,
    ...(response.duration_ticks === null ? {} : { durationTicks: response.duration_ticks }),
    canSeek: response.can_seek,
    playbackBootstrapUrl: response.playback_bootstrap_url,
    playbackCapability: response.playback_capability,
    audioTracks: response.audio_tracks.map(mapTrack),
    subtitleTracks: response.subtitle_tracks.map(mapTrack),
    ...(response.previous_target_id === null ? {} : { previousTargetId: response.previous_target_id }),
    ...(response.next_target_id === null ? {} : { nextTargetId: response.next_target_id })
  });
}
