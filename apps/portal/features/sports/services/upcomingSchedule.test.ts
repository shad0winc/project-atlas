import { describe, expect, it } from "vitest";
import type { SportsEvent, SportsFollow } from "../types/sports";
import { reconcileUpcomingSchedule, selectedUpcomingSchedule } from "./upcomingSchedule";
const now = Date.parse("2026-10-31T12:00:00Z");
const event = (id: string, league: string, provider = "thesportsdb"): SportsEvent => ({
  provider, providerEventId: id, providerLeagueId: league, homeTeamId: "home", awayTeamId: "away",
  name: id, sport: "Sport", league, startAt: new Date(now + 3600000).toISOString(), status: "scheduled", requested: false,
});
const follows: SportsFollow[] = ["nba", "nfl"].map(id => ({
  subscriptionId: id, provider: "thesportsdb", providerId: id, type: "league", name: id,
  enabled: true, userId: "owner", record: false, createdAt: null,
}));
const ok = (value: SportsEvent[]): PromiseFulfilledResult<SportsEvent[]> => ({ status: "fulfilled", value });
describe("upcoming selection and retained schedule", () => {
  const snapshot = reconcileUpcomingSchedule({}, ["thesportsdb"], [ok([event("basketball", "nba"), event("football", "nfl")])], now);
  it("shows only NBA when an NBA card is selected", () => {
    expect(selectedUpcomingSchedule(snapshot, follows, { provider: "thesportsdb", type: "league", providerId: "nba" }, now).map(e => e.name)).toEqual(["basketball"]);
  });
  it("all followed restores both leagues; unfollowed identities disappear", () => {
    expect(selectedUpcomingSchedule(snapshot, follows, undefined, now)).toHaveLength(2);
    expect(selectedUpcomingSchedule(snapshot, follows.slice(1), undefined, now).map(e => e.name)).toEqual(["football"]);
  });
  it("a failed refresh keeps the last schedule and its original load time", () => {
    const next = reconcileUpcomingSchedule(snapshot, ["thesportsdb"], [{ status: "rejected", reason: { status: 429 } }], now + 60000);
    expect(next).toEqual(snapshot);
  });
  it("a successful empty response and a final status remove old scheduled rows", () => {
    expect(selectedUpcomingSchedule(reconcileUpcomingSchedule(snapshot, ["thesportsdb"], [ok([])], now), follows, undefined, now)).toEqual([]);
    expect(selectedUpcomingSchedule(reconcileUpcomingSchedule(snapshot, ["thesportsdb"], [ok([{ ...event("basketball", "nba"), status: "final" }])], now), follows, undefined, now)).toEqual([]);
  });
  it("retention cannot keep past games or mix provider identities", () => {
    expect(selectedUpcomingSchedule(snapshot, follows, undefined, now + 7200000)).toEqual([]);
    expect(selectedUpcomingSchedule(snapshot, follows, { provider: "other", type: "league", providerId: "nba" }, now)).toEqual([]);
  });
  it("team selection matches either side and excludes unrelated games", () => {
    expect(selectedUpcomingSchedule(snapshot, follows, { provider: "thesportsdb", type: "team", providerId: "away" }, now)).toHaveLength(2);
    expect(selectedUpcomingSchedule(snapshot, follows, { provider: "thesportsdb", type: "team", providerId: "unrelated" }, now)).toEqual([]);
  });
});
