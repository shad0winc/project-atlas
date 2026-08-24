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
