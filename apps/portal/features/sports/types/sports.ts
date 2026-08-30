export type SportsEvent = Readonly<{
  provider: string;
  providerEventId: string;
  name: string;
  sport: string;
  league: string;
  startAt: string;
  status: string;
  requested: boolean;
}>;

export type SportsSubscription = Readonly<{
  subscriptionId: string;
  type: "event";
  provider: string;
  providerEventId: string;
  name: string;
  userId: string;
  enabled: boolean;
  createdAt: string;
}>;

export type SportsEventTransport = Readonly<{
  provider: string;
  provider_event_id: string;
  name: string;
  sport: string;
  league: string;
  start_at: string;
  status: string;
  requested: boolean;
}>;

export type SportsEventCollectionTransport = Readonly<{
  events: readonly SportsEventTransport[];
}>;

export type SportsSubscriptionTransport = Readonly<{
  subscription_id: string;
  type: string;
  provider: string;
  provider_event_id: string;
  name: string;
  user_id: string;
  enabled: boolean;
  created_at: string;
}>;

export type SportsSearchResult = Readonly<{ id: string; name: string; sport: string; league: string; }>;
export type SportsSearchCollectionTransport = Readonly<{ results: readonly Readonly<{ id: string; name: string; sport?: string; league?: string; }>[]; }>;
export type SportsFollow = Readonly<{ subscriptionId: string; type: "event" | "team" | "league"; provider: string; providerId: string; name: string; userId: string; enabled: boolean; record: boolean; createdAt: string | null; }>;
export type SportsFollowTransport = Readonly<{ subscription_id: string; type: string; provider: string; provider_id: string; name: string; user_id: string; enabled: boolean; record?: boolean; created_at?: string | null; }>;
export type SportsFollowCollectionTransport = Readonly<{ subscriptions: readonly SportsFollowTransport[]; }>;

function requiredText(value: unknown, fieldName: string): string {
  const normalized = String(value ?? "").trim();

  if (!normalized) {
    throw new Error(`${fieldName} must not be empty.`);
  }

  return normalized;
}

function normalizedTimestamp(value: unknown, fieldName: string): string {
  const normalized = requiredText(value, fieldName);

  const parsed = new Date(normalized);

  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`${fieldName} must be a valid timestamp.`);
  }

  return parsed.toISOString();
}

export function createSportsEvent(input: SportsEventTransport): SportsEvent {
  return Object.freeze({
    provider: requiredText(input.provider, "sportsEvent.provider"),
    providerEventId: requiredText(input.provider_event_id, "sportsEvent.providerEventId"),
    name: requiredText(input.name, "sportsEvent.name"),
    sport: requiredText(input.sport, "sportsEvent.sport"),
    league: requiredText(input.league, "sportsEvent.league"),
    startAt: normalizedTimestamp(input.start_at, "sportsEvent.startAt"),
    status: requiredText(input.status, "sportsEvent.status"),
    requested: Boolean(input.requested)
  });
}

export function createSportsEventCollection(
  input: SportsEventCollectionTransport
): readonly SportsEvent[] {
  return Object.freeze(input.events.map(createSportsEvent));
}

export function createSportsSubscription(input: SportsSubscriptionTransport): SportsSubscription {
  const type = requiredText(input.type, "sportsSubscription.type");

  if (type !== "event") {
    throw new Error("sportsSubscription.type must be event.");
  }

  return Object.freeze({
    subscriptionId: requiredText(input.subscription_id, "sportsSubscription.subscriptionId"),
    type: "event",
    provider: requiredText(input.provider, "sportsSubscription.provider"),
    providerEventId: requiredText(input.provider_event_id, "sportsSubscription.providerEventId"),
    name: requiredText(input.name, "sportsSubscription.name"),
    userId: requiredText(input.user_id, "sportsSubscription.userId"),
    enabled: Boolean(input.enabled),
    createdAt: normalizedTimestamp(input.created_at, "sportsSubscription.createdAt")
  });
}

export function createSportsSearchCollection(input: SportsSearchCollectionTransport): readonly SportsSearchResult[] {
  return Object.freeze(input.results.map((item) => Object.freeze({ id: requiredText(item.id, "sportsSearch.id"), name: requiredText(item.name, "sportsSearch.name"), sport: String(item.sport ?? "").trim(), league: String(item.league ?? "").trim() })));
}
export function createSportsFollow(input: SportsFollowTransport): SportsFollow {
  const type = requiredText(input.type, "sportsFollow.type");
  if (type !== "event" && type !== "team" && type !== "league") throw new Error("sportsFollow.type must be event, team, or league.");
  return Object.freeze({ subscriptionId: requiredText(input.subscription_id, "sportsFollow.subscriptionId"), type, provider: requiredText(input.provider, "sportsFollow.provider"), providerId: requiredText(input.provider_id, "sportsFollow.providerId"), name: requiredText(input.name, "sportsFollow.name"), userId: requiredText(input.user_id, "sportsFollow.userId"), enabled: Boolean(input.enabled), record: Boolean(input.record), createdAt: input.created_at ? normalizedTimestamp(input.created_at, "sportsFollow.createdAt") : null });
}
export function createSportsFollowCollection(input: SportsFollowCollectionTransport): readonly SportsFollow[] { return Object.freeze(input.subscriptions.map(createSportsFollow)); }
