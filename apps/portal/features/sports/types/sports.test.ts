import { describe, expect, it } from "vitest";

import { createSportsEvent, createSportsEventCollection, createSportsSubscription } from "./sports";

describe("Sports Portal types", () => {
  it("preserves provider and provider-event identity", () => {
    const event = createSportsEvent({
      provider: " thesportsdb ",
      provider_event_id: " event-001 ",
      name: " Atlas United vs Atlas City ",
      sport: " Soccer ",
      league: " Atlas Test League ",
      start_at: "2026-08-17T20:00:00Z",
      status: " scheduled ",
      requested: false
    });

    expect(event.provider).toBe("thesportsdb");
    expect(event.providerEventId).toBe("event-001");
    expect(event.name).toBe("Atlas United vs Atlas City");
    expect(event.sport).toBe("Soccer");
    expect(event.league).toBe("Atlas Test League");
    expect(event.status).toBe("scheduled");
    expect(event.requested).toBe(false);
  });

  it("rejects empty provider identity", () => {
    expect(() =>
      createSportsEvent({
        provider: " ",
        provider_event_id: "event-001",
        name: "Atlas United vs Atlas City",
        sport: "Soccer",
        league: "Atlas Test League",
        start_at: "2026-08-17T20:00:00Z",
        status: "scheduled",
        requested: false
      })
    ).toThrow();
  });

  it("keeps Atlas subscription and provider-event IDs distinct", () => {
    const subscription = createSportsSubscription({
      subscription_id: "sub-atlas-001",
      type: "event",
      provider: "thesportsdb",
      provider_event_id: "event-001",
      name: "Atlas United vs Atlas City",
      user_id: "usr-atlas-001",
      enabled: true,
      created_at: "2026-08-16T20:00:00Z"
    });

    expect(subscription.subscriptionId).toBe("sub-atlas-001");
    expect(subscription.providerEventId).toBe("event-001");
    expect(subscription.subscriptionId).not.toBe(subscription.providerEventId);
    expect(subscription.userId).toBe("usr-atlas-001");
  });

  it("builds immutable event collections", () => {
    const collection = createSportsEventCollection({
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

    expect(collection).toHaveLength(1);
    expect(collection[0]?.providerEventId).toBe("event-001");
  });
});
