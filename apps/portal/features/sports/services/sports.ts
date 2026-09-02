import { AtlasApiError } from "../../../lib/api/errors";
import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createSportsEventCollection,
  createSportsEventSearchCollection,
  createSportsFollow,
  createSportsFollowCollection,
  createSportsSearchCollection,
  createSportsSubscription,
  type SportsEvent,
  type SportsEventCollectionTransport,
  type SportsFollow,
  type SportsFollowCollectionTransport,
  type SportsFollowTransport,
  type SportsSearchCollectionTransport,
  type SportsSearchResult,
  type SportsSearchType,
  type SportsSubscription,
  type SportsSubscriptionTransport
} from "../types/sports";

export type SportsEventRequestInput = Readonly<{
  provider: string;
  providerEventId: string;
}>;

export type SportsRequestOptions = Readonly<{
  signal?: AbortSignal;
}>;

export type SportsEventFilter = Readonly<{ teamIds?: readonly string[]; leagueIds?: readonly string[]; }>;

export async function loadSportsEvents(options: SportsRequestOptions = {}, filter: SportsEventFilter = {}): Promise<readonly SportsEvent[]> {
  const params = new URLSearchParams({ provider: "thesportsdb" });
  for (const id of filter.teamIds ?? []) if (id.trim()) params.append("team_id", id.trim());
  for (const id of filter.leagueIds ?? []) if (id.trim()) params.append("league_id", id.trim());
  const response = await authenticatedAtlasApiRequest<SportsEventCollectionTransport>(
    `/sports/events?${params.toString()}`,
    {
      method: "GET",
      cache: "no-store",
      signal: options.signal
    }
  );

  return createSportsEventCollection(response);
}

export async function requestSportsEvent(
  input: SportsEventRequestInput,
  options: SportsRequestOptions = {}
): Promise<SportsSubscription> {
  const provider = input.provider.trim();
  const providerEventId = input.providerEventId.trim();

  if (!provider) {
    throw new Error("sportsRequest.provider must not be empty.");
  }

  if (!providerEventId) {
    throw new Error("sportsRequest.providerEventId must not be empty.");
  }

  const response = await authenticatedAtlasApiRequest<SportsSubscriptionTransport>(
    "/sports/subscriptions",
    {
      method: "POST",
      cache: "no-store",
      signal: options.signal,
      body: {
        provider,
        provider_event_id: providerEventId
      },
      retryPolicy: {
        maxRetries: 0,
        baseDelayMs: 250,
        maxDelayMs: 5_000
      }
    }
  );

  return createSportsSubscription(response);
}

export async function searchSports(
  type: SportsSearchType,
  query: string,
  options: SportsRequestOptions = {}
): Promise<readonly SportsSearchResult[]> {
  const normalizedQuery = query.trim();

  if (!normalizedQuery) {
    return [];
  }

  const path = type === "team" ? "teams" : type === "league" ? "leagues" : "events";

  try {
    const requestOptions = {
      method: "GET" as const,
      cache: "no-store" as const,
      signal: options.signal,
      retryPolicy: {
        maxRetries: 0,
        baseDelayMs: 250,
        maxDelayMs: 5_000
      }
    };

    if (type === "event") {
      const response =
        await authenticatedAtlasApiRequest<SportsEventCollectionTransport>(
          `/sports/search/${path}?provider=thesportsdb&query=${encodeURIComponent(normalizedQuery)}`,
          requestOptions
        );
      return createSportsEventSearchCollection(response);
    }

    const response =
      await authenticatedAtlasApiRequest<SportsSearchCollectionTransport>(
        `/sports/search/${path}?provider=thesportsdb&query=${encodeURIComponent(normalizedQuery)}`,
        requestOptions
      );

    return createSportsSearchCollection(type, response);
  } catch (error) {
    if (
      error instanceof AtlasApiError &&
      error.kind === "rate-limit"
    ) {
      throw new Error(
        "Sports search is temporarily rate limited. "
          + "Please try again shortly."
      );
    }

    throw error;
  }
}

export async function loadSportsFollows(options: SportsRequestOptions = {}): Promise<readonly SportsFollow[]> { return createSportsFollowCollection(await authenticatedAtlasApiRequest<SportsFollowCollectionTransport>("/sports/follows", { method: "GET", cache: "no-store", signal: options.signal })); }
export async function followSports(type: "event" | "team" | "league", providerId: string, options: SportsRequestOptions = {}): Promise<SportsFollow> {
  const id=providerId.trim(); if (!id) throw new Error("sportsFollow.providerId must not be empty.");
  return createSportsFollow(await authenticatedAtlasApiRequest<SportsFollowTransport>("/sports/follows", { method: "POST", cache: "no-store", signal: options.signal, body: { type, provider: "thesportsdb", provider_id: id }, retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5000 } }));
}
export async function unfollowSports(subscriptionId: string, options: SportsRequestOptions = {}): Promise<void> {
  const id=subscriptionId.trim(); if (!id) throw new Error("sportsFollow.subscriptionId must not be empty.");
  await authenticatedAtlasApiRequest<unknown>(`/sports/follows/${encodeURIComponent(id)}`, { method: "DELETE", cache: "no-store", signal: options.signal });
}

export async function updateSportsRecordingIntent(
  subscriptionId: string,
  record: boolean,
  options: SportsRequestOptions = {}
): Promise<SportsFollow> {
  const id = subscriptionId.trim();
  if (!id) throw new Error("sportsFollow.subscriptionId must not be empty.");
  return createSportsFollow(
    await authenticatedAtlasApiRequest<SportsFollowTransport>(
      `/sports/follows/${encodeURIComponent(id)}/recording`,
      { method: "PATCH", cache: "no-store", signal: options.signal, body: { record },
        retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5_000 } }
    )
  );
}
