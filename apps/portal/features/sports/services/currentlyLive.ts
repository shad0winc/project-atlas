import type { SportsEvent, SportsFollow } from "../types/sports";

export function followedLiveEvents(
  events: readonly SportsEvent[],
  follows: readonly SportsFollow[],
  now = Date.now(),
): readonly SportsEvent[] {
  const seen = new Set<string>();
  return events
    .filter((event) => {
      const key = `${event.provider}:${event.providerEventId}`;
      const start = Date.parse(event.startAt);
      const needsMetadataAge = event.provider === "espn" || event.metadataObservedAt !== undefined || event.metadataExpiresAt !== undefined;
      const observed = Date.parse(event.metadataObservedAt ?? "");
      const expires = Date.parse(event.metadataExpiresAt ?? "");
      const metadataFresh = !needsMetadataAge || (
        Number.isFinite(observed) && Number.isFinite(expires) &&
        observed <= now && now < expires && expires > observed && expires - observed <= 3_600_000
      );
      if (
        !metadataFresh ||
        seen.has(key) ||
        event.status !== "live" ||
        !Number.isFinite(start) ||
        start > now
      )
        return false;
      const matched = follows.some(
        (follow) =>
          follow.enabled &&
          follow.provider === event.provider &&
          ((follow.type === "event" &&
            follow.providerId === event.providerEventId) ||
            (follow.type === "team" &&
              (follow.providerId === event.homeTeamId ||
                follow.providerId === event.awayTeamId)) ||
            (follow.type === "league" &&
              follow.providerId === event.providerLeagueId)),
      );
      if (matched) seen.add(key);
      return matched;
    })
    .sort((a, b) => Date.parse(a.startAt) - Date.parse(b.startAt));
}

export function sportsLocalStart(startAt: string): string {
  const date = new Date(startAt);
  if (!Number.isFinite(date.getTime())) return "Start time unavailable";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "long",
  }).format(date);
}
