import type { SportsEvent } from "../types/sports";

/** A rolling seven-day window; playback availability is a separate contract. */
export function upcomingSportsEvents(
  events: readonly SportsEvent[],
  now = Date.now(),
): readonly SportsEvent[] {
  const end = now + 7 * 24 * 60 * 60 * 1000;
  const unique = new Map<string, SportsEvent>();
  for (const event of events) {
    // Replace by identity before filtering so a rescheduled/final record wins.
    unique.set(`${event.provider}:${event.providerEventId}`, event);
  }
  return [...unique.values()]
    .filter((event) => {
      const start = Date.parse(event.startAt);
      return (
        event.status === "scheduled" &&
        Number.isFinite(start) &&
        start >= now &&
        start <= end
      );
    })
    .sort((left, right) => Date.parse(left.startAt) - Date.parse(right.startAt));
}
