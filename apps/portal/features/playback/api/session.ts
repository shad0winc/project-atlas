import { resolvePlaybackSession } from "../services/session";
import type { PlaybackSession } from "../types/session";

export async function loadPlaybackSession(
  provider: string,
  itemId: string,
  signal?: AbortSignal
): Promise<PlaybackSession> {
  return resolvePlaybackSession(provider, itemId, signal);
}
