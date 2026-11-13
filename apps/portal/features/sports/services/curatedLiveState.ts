import type { SportsEvent } from "../types/sports";

export function curatedEventFresh(event: SportsEvent, now = Date.now()): boolean {
  const observed = Date.parse(event.metadataObservedAt ?? "");
  const expires = Date.parse(event.metadataExpiresAt ?? "");
  return Number.isFinite(observed) && Number.isFinite(expires) && observed <= now && now < expires;
}

export function mergeSportsObservations(...groups: readonly (readonly SportsEvent[])[]): readonly SportsEvent[] {
  const rows = new Map<string, SportsEvent>();
  for (const group of groups) for (const event of group) {
    const key = `${event.provider}:${event.providerEventId}`;
    const old = rows.get(key);
    const observed = Date.parse(event.metadataObservedAt ?? "");
    const previous = Date.parse(old?.metadataObservedAt ?? "");
    if (!old || (Number.isFinite(observed) && (!Number.isFinite(previous) || observed >= previous))) rows.set(key, event);
  }
  return [...rows.values()];
}

export function retainFollowedLiveObservations(
  previous: readonly SportsEvent[],
  providers: readonly string[],
  results: readonly PromiseSettledResult<readonly SportsEvent[]>[],
): readonly SportsEvent[] {
  const succeeded = new Set(providers.filter((_, index) => results[index]?.status === "fulfilled"));
  const received = results.flatMap((result, index) =>
    result.status === "fulfilled" ? result.value.filter(event => event.provider === providers[index]) : []);
  const incomingKeys = new Set(received.map(event => `${event.provider}:${event.providerEventId}`));
  return mergeSportsObservations(previous.filter(event =>
    !succeeded.has(event.provider) || incomingKeys.has(`${event.provider}:${event.providerEventId}`)), received);
}

export function curatedStartLabel(startAt: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "long" }).format(new Date(startAt));
}
