import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  authenticatedAtlasApiRequest: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: mocks.authenticatedAtlasApiRequest
}));

import { loadSportsEvents, requestSportsEvent, searchSports } from "./sports";

describe("Sports Portal service", () => {
  beforeEach(() => {
    mocks.authenticatedAtlasApiRequest.mockReset();
  });

  it("loads authenticated Sports events", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      events: [
        {
          provider: "thesportsdb",
          provider_event_id: "event-001",
          name: "Atlas United vs Atlas City",
          sport: "Soccer",
          league: "Atlas Test League",
          start_at: "2026-08-17T20:00:00Z",
          status: "scheduled",
          requested: false
        }
      ]
    });

    const events = await loadSportsEvents();

    expect(mocks.authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/events?provider=thesportsdb",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );

    expect(events).toHaveLength(1);

    expect(events[0]?.providerEventId).toBe("event-001");
  });

  it("requests only provider identity from the browser", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      subscription_id: "sub-atlas-001",
      type: "event",
      provider: "thesportsdb",
      provider_event_id: "event-001",
      name: "Atlas United vs Atlas City",
      user_id: "usr-atlas-001",
      enabled: true,
      created_at: "2026-08-16T20:00:00Z"
    });

    const subscription = await requestSportsEvent({
      provider: "thesportsdb",
      providerEventId: "event-001"
    });

    expect(mocks.authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/subscriptions",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        body: {
          provider: "thesportsdb",
          provider_event_id: "event-001"
        },
        retryPolicy: expect.objectContaining({
          maxRetries: 0
        })
      })
    );

    expect(subscription.userId).toBe("usr-atlas-001");

    expect(subscription.providerEventId).toBe("event-001");
  });

  it("does not expose server-owned identity in request input", () => {
    const input = {
      provider: "thesportsdb",
      providerEventId: "event-001"
    };

    expect(input).not.toHaveProperty("userId");
    expect(input).not.toHaveProperty("subscriptionId");
    expect(input).not.toHaveProperty("name");
    expect(input).not.toHaveProperty("type");
  });
  it("searches upcoming Sports events through the event contract", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      events: [
        {
          provider: "thesportsdb",
          provider_event_id: "event-090",
          name: "Detroit Lions vs New Orleans Saints",
          sport: "American Football",
          league: "NFL",
          start_at: "2026-09-06T17:00:00Z",
          status: "scheduled",
          requested: false
        }
      ]
    });

    const results = await searchSports("event", "Lions");

    expect(mocks.authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/search/events?provider=thesportsdb&query=Lions",
      expect.objectContaining({ method: "GET", cache: "no-store" })
    );
    expect(results[0]).toMatchObject({
      kind: "event",
      id: "event-090",
      name: "Detroit Lions vs New Orleans Saints",
      status: "scheduled",
      requested: false
    });
  });
});
