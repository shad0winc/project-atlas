import type { SportsEvent, SportsFollow } from "../types/sports";
import { upcomingSportsEvents } from "./upcomingSports";

export type UpcomingSelection = Readonly<{
  provider: string;
  type: "team" | "league";
  providerId: string;
}>;
export type UpcomingSnapshot = Readonly<Record<string, Readonly<{
  events: readonly SportsEvent[];
  loadedAt: number;
}>>>;

/** Scheduled metadata can remain visible on failure; it never establishes live availability. */
export function reconcileUpcomingSchedule(
  current: UpcomingSnapshot,
  providers: readonly string[],
  results: readonly PromiseSettledResult<readonly SportsEvent[]>[],
  now = Date.now(),
): UpcomingSnapshot {
  const next = { ...current };
  results.forEach((result, index) => {
    const provider = providers[index];
    if (provider !== undefined && result.status === "fulfilled") {
      next[provider] = {
        events: result.value.filter(event => event.provider === provider),
        loadedAt: now,
      };
    }
  });
  return next;
}

export function selectedUpcomingSchedule(
  snapshot: UpcomingSnapshot,
  follows: readonly SportsFollow[],
  selection?: UpcomingSelection,
  now = Date.now(),
): readonly SportsEvent[] {
  const identities = selection ? [selection] : follows.filter(follow => follow.enabled && follow.type !== "channel");
  return upcomingSportsEvents(Object.values(snapshot).flatMap(value => value.events).filter(event =>
    identities.some(identity => identity.provider === event.provider && (
      (identity.type === "event" && identity.providerId === event.providerEventId) ||
      (identity.type === "league" && identity.providerId === event.providerLeagueId) ||
      (identity.type === "team" && (identity.providerId === event.homeTeamId || identity.providerId === event.awayTeamId))
    )),
  ), now);
}

export function upcomingLastLoadedAt(snapshot: UpcomingSnapshot, follows: readonly SportsFollow[], selection?: UpcomingSelection): number | undefined {
  const providers = selection ? [selection.provider] : [...new Set(follows.filter(f => f.enabled && f.type !== "channel").map(f => f.provider))];
  const stamps = providers.flatMap(provider => snapshot[provider] ? [snapshot[provider].loadedAt] : []);
  return stamps.length ? Math.min(...stamps) : undefined;
}
