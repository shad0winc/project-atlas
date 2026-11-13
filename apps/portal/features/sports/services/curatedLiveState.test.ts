import assert from "node:assert/strict";
import { describe, it } from "vitest";
import { curatedEventFresh, curatedStartLabel, mergeSportsObservations, retainFollowedLiveObservations } from "./curatedLiveState";
import { followedLiveEvents } from "./currentlyLive";
import type { SportsEvent, SportsFollow } from "../types/sports";

const now = Date.parse("2026-11-01T00:12:00Z");
const event: SportsEvent = { provider: "espn", providerEventId: "basketball-nba-401909900",
  providerLeagueId: "basketball/nba", homeTeamId: "basketball-nba-15", awayTeamId: "basketball-nba-5",
  name: "Cavaliers at Bucks", sport: "Basketball", league: "NBA", startAt: "2026-11-01T00:00:00Z",
  status: "live", requested: false, metadataObservedAt: "2026-11-01T00:10:00Z", metadataExpiresAt: "2026-11-01T00:15:00Z" };
const follow: SportsFollow = { subscriptionId: "fixture", type: "team", provider: "espn", providerId: "basketball-nba-5",
  name: "Cavaliers", userId: "fixture", enabled: true, record: false, createdAt: null };

describe("curated live observation integration", () => {
  it("retains a followed event on lookup failure only while its observation is fresh", () => {
    const rows = retainFollowedLiveObservations([event], ["espn"], [
      { status: "rejected", reason: new Error("503") },
    ]);
    assert.deepEqual(followedLiveEvents(rows, [follow], now), [event]);
    assert.deepEqual(followedLiveEvents(rows, [follow], now + 300_000), []);
    const ended = { ...event, status: "final", metadataObservedAt: "2026-11-01T00:11:00Z" };
    const refreshed = retainFollowedLiveObservations(rows, ["espn"], [{ status: "fulfilled", value: [ended] }]);
    assert.deepEqual(followedLiveEvents(refreshed, [follow], now), []);
  });

  it("accepts a current provider observation", () => assert.equal(curatedEventFresh(event, now), true));
  it("does not keep expired live claims", () => assert.equal(curatedEventFresh(event, now + 300_000), false));
  it("does not accept missing observation ages", () => assert.equal(curatedEventFresh({ ...event, metadataObservedAt: undefined }, now), false));
  it("publishes a curated home or away follow to Currently Live", () => {
    assert.equal(followedLiveEvents(mergeSportsObservations([], [event]), [follow], now).length, 1);
    assert.equal(followedLiveEvents([event], [{ ...follow, providerId: "basketball-nba-15" }], now).length, 1);
  });
  it("preserves source identities instead of guessing cross-provider aliases", () => {
    assert.equal(followedLiveEvents([event], [{ ...follow, provider: "thesportsdb" }], now).length, 0);
    assert.equal(mergeSportsObservations([event], [{ ...event, provider: "thesportsdb" }]).length, 2);
  });
  it("a newer final observation supersedes an older live row", () => {
    const revised = { ...event, status: "final", metadataObservedAt: "2026-11-01T00:11:00Z" };
    assert.equal(followedLiveEvents(mergeSportsObservations([event], [revised]), [follow], now).length, 0);
  });
  it("an older curated row cannot overwrite a newer cancellation", () => {
    const revised = { ...event, status: "cancelled", metadataObservedAt: "2026-11-01T00:11:00Z" };
    assert.equal(mergeSportsObservations([revised], [event])[0].status, "cancelled");
  });
  it("valid observation ages supersede missing ages", () => {
    assert.equal(mergeSportsObservations([{ ...event, metadataObservedAt: undefined }], [event])[0], event);
  });
  it("deduplicates the same source and event", () => assert.equal(mergeSportsObservations([event], [event]).length, 1));
  it("includes a timezone in the displayed start", () => {
    const text = curatedStartLabel(event.startAt);
    assert.ok(text.length > 10);
    assert.notEqual(text, new Date(event.startAt).toLocaleDateString());
  });
});
