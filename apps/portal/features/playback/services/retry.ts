import type { PlaybackSession } from "../types/session";
import type { SubtitleSelection } from "./session";

export function adminPlaybackRefreshDelay(accessToken: string, now = Date.now()): number | null {
  try {
    const payload = accessToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp, iat } = JSON.parse(atob(payload));
    if (!Number.isSafeInteger(exp) || !Number.isSafeInteger(iat) || exp <= iat) return null;
    const lead = Math.min(60_000, (exp - iat) * 100);
    return Math.max(0, exp * 1_000 - now - lead);
  } catch {
    return null;
  }
}

export type PlaybackSessionResolver = (
  provider: string,
  itemId: string,
  signal?: AbortSignal,
  subtitle?: SubtitleSelection
) => Promise<PlaybackSession>;

export function retryResumePosition(
  canSeek: boolean,
  current: number | undefined,
  saved: number | null
): number | null {
  if (!canSeek) return null;
  if (current !== undefined && Number.isFinite(current) && current > 0) {
    return current;
  }
  return saved !== null && Number.isFinite(saved) && saved > 0 ? saved : null;
}

export async function refreshPlaybackForRetry(
  session: PlaybackSession,
  resolver: PlaybackSessionResolver,
  subtitle: SubtitleSelection,
  signal: AbortSignal
): Promise<PlaybackSession> {
  signal.throwIfAborted();
  const refreshed = await resolver(session.provider, session.playableTargetId, signal, subtitle);
  signal.throwIfAborted();
  if (!refreshed.available || !refreshed.playbackCapability.trim()) {
    throw new Error("Playback is not currently available.");
  }
  // Always replace the session object so the player exchanges the fresh capability.
  return { ...refreshed };
}
