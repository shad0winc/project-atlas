import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createSportsEventCollection,
  createSportsSubscription,
  type SportsEvent,
  type SportsEventCollectionTransport,
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

export async function loadSportsEvents(
  options: SportsRequestOptions = {}
): Promise<readonly SportsEvent[]> {
  const response = await authenticatedAtlasApiRequest<SportsEventCollectionTransport>(
    "/sports/events?provider=thesportsdb",
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
