import type { PlaybackSession } from "../types/session";

export function episodeHref(provider: string, itemId: string): string {
  return `/portal/theater?provider=${encodeURIComponent(provider)}&item=${encodeURIComponent(itemId)}`;
}

export function nextEpisodeTarget(session: PlaybackSession, enabled: boolean): string | null {
  if (!enabled || !session.available || session.sourceType !== "library" || !session.seriesId ||
      !session.nextTargetId || session.nextTargetId === session.playableTargetId) return null;
  return session.nextTargetId;
}
