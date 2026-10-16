import { describe, expect, it } from "vitest";

import { createSportsEvent, createSportsEventCollection, createSportsEventSearchCollection, createSportsSearchCollection, createSportsSubscription } from "./sports";

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

  it("creates discriminated team and event search results", () => {
    const teams = createSportsSearchCollection("team", {
      results: [{ id: "team-001", name: "Detroit Lions", sport: "American Football", league: "NFL" }]
    });
    const events = createSportsEventSearchCollection({
      events: [{ provider: "thesportsdb", provider_event_id: "event-090", name: "Detroit Lions vs New Orleans Saints", sport: "American Football", league: "NFL", start_at: "2026-09-06T17:00:00Z", status: "scheduled", requested: false }]
    });
    expect(teams[0]?.kind).toBe("team");
    expect(events[0]?.kind).toBe("event");
    expect(events[0]?.id).toBe("event-090");
  });
});


describe("Sports metadata observation transport", () => {
  const raw = { provider: "espn", provider_event_id: "football-nfl-1", name: "Game", sport: "Football", league: "NFL", start_at: "2026-10-16T12:00:00Z", status: "live", requested: false };
  it("preserves original metadata observation and expiry", () => {
    const event = createSportsEvent({ ...raw, metadata_observed_at: "2026-10-16T12:00:00Z", metadata_expires_at: "2026-10-16T12:01:00Z" });
    expect(event.metadataExpiresAt).toBe("2026-10-16T12:01:00.000Z");
    expect(event.metadataObservedAt).toBe("2026-10-16T12:00:00.000Z");
  });
  it("rejects partial, naive, reversed and excessive lifetimes", () => {
    for (const age of [
      { metadata_observed_at: "2026-10-16T12:00:00Z" },
      { metadata_observed_at: "2026-10-16T12:00:00", metadata_expires_at: "2026-10-16T12:01:00Z" },
      { metadata_observed_at: "2026-10-16T12:00:00Z", metadata_expires_at: "2026-10-16T11:59:00Z" },
      { metadata_observed_at: "2026-10-16T12:00:00Z", metadata_expires_at: "2026-10-16T14:00:00Z" },
    ]) expect(() => createSportsEvent({ ...raw, ...age })).toThrow();
  });
});
