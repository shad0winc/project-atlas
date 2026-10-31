import assert from "node:assert/strict";
import { describe, it } from "vitest";
import { curatedWindow, filterCuratedTeam, parseCuratedSchedule, parseCuratedTeams, retainCuratedSchedule } from "./curatedSchedule";

const window = { startAt: "2026-10-31T00:00:00Z", endAt: "2026-11-01T00:00:00Z" };
function document() {
  return {
    version: 1, competition_id: "nfl", provider: "espn", provider_league_id: "football/nfl",
    start_at: window.startAt, end_at: window.endAt, evaluated_at: "2026-10-31T12:00:00Z",
    observed_at: "2026-10-31T11:59:00Z", expires_at: "2026-10-31T12:00:00Z",
    status: "ready", coverage_complete: true, provider_completeness_proven: false,
    required_buckets: 3, fresh_buckets: 3, retry_after_seconds: 0,
    events: [{ provider: "espn", provider_event_id: "football-nfl-123", name: "Fixture teams", sport: "Football", league: "NFL",
      provider_league_id: "football/nfl", home_team_id: "football-nfl-1", away_team_id: "football-nfl-2",
      start_at: "2026-10-31T20:00:00Z", status: "scheduled", requested: false,
      metadata_observed_at: "2026-10-31T11:59:00Z", metadata_expires_at: "2026-10-31T12:00:00Z" }],
  };
}

describe("curated cached schedules", () => {
  it("preserves source identities and observation ages", () => {
    const result = parseCuratedSchedule(document(), "nfl", window);
    assert.equal(result.events[0].providerEventId, "football-nfl-123");
    assert.equal(result.events[0].metadataObservedAt, "2026-10-31T11:59:00.000Z");
  });
  it("refuses another competition", () => assert.throws(() => parseCuratedSchedule(document(), "nba", window)));
  it("refuses events from another route", () => {
    const value = document(); value.events[0].provider_league_id = "basketball/nba";
    assert.throws(() => parseCuratedSchedule(value, "nfl", window));
  });
  it("refuses events outside the requested dates", () => {
    const value = document(); value.events[0].start_at = window.endAt;
    assert.throws(() => parseCuratedSchedule(value, "nfl", window));
  });
  it("refuses false coverage claims", () => {
    const value = document(); value.fresh_buckets = 2;
    assert.throws(() => parseCuratedSchedule(value, "nfl", window));
  });
  it("distinguishes preparing from checked empty", () => {
    const value = document(); value.events = [];
    assert.equal(parseCuratedSchedule(value, "nfl", window).coverageComplete, true);
    Object.assign(value, { status: "preparing", fresh_buckets: 0, coverage_complete: false });
    assert.equal(parseCuratedSchedule(value, "nfl", window).coverageComplete, false);
  });
  it("retains events and their original ages through an incomplete refresh", () => {
    const old = parseCuratedSchedule(document(), "nfl", window);
    const value = document(); value.events = []; Object.assign(value, { status: "preparing", fresh_buckets: 0, coverage_complete: false, observed_at: null, expires_at: null });
    const result = retainCuratedSchedule(old, parseCuratedSchedule(value, "nfl", window));
    assert.equal(result.events.length, 1); assert.equal(result.observedAt, old.observedAt); assert.equal(result.retained, true);
  });
  it("accepts a newer confirmed empty schedule", () => {
    const old = parseCuratedSchedule(document(), "nfl", window), value = document(); value.events = [];
    assert.equal(retainCuratedSchedule(old, parseCuratedSchedule(value, "nfl", window)).events.length, 0);
  });
  it("does not resurrect events removed by a partial newer observation", () => {
    const old = parseCuratedSchedule(document(), "nfl", window), value = document(); value.events = [];
    Object.assign(value, { status: "partial", coverage_complete: false, fresh_buckets: 1 });
    assert.equal(retainCuratedSchedule(old, parseCuratedSchedule(value, "nfl", window)).events.length, 0);
  });
  it("filters home and away teams locally", () => {
    const value = parseCuratedSchedule(document(), "nfl", window);
    for (const id of ["", "football-nfl-1", "football-nfl-2"]) assert.equal(filterCuratedTeam(value, id).length, 1);
    assert.equal(filterCuratedTeam(value, "football-nfl-3").length, 0);
  });
  it("refuses a directory with cross-route identities", () => {
    assert.throws(() => parseCuratedTeams({ version: 1, evaluated_at: "2026-10-31T12:00:00Z", competition_id: "nfl", provider: "espn", provider_league_id: "football/nfl", status: "ready", teams: [{ id: "basketball-nba-1", name: "Fixture" }] }, "nfl"));
  });
  it("keeps the next seven days within 168 hours across timezone changes", () => {
    const value = curatedWindow("week", new Date("2026-10-31T12:00:00-04:00"));
    assert.equal(Date.parse(value.endAt) - Date.parse(value.startAt), 168 * 3600_000);
  });
  it("uses local midnight for individual days", () => {
    const value = curatedWindow("tomorrow", new Date(2026, 9, 31, 12));
    assert.equal(new Date(value.startAt).getDate(), 1); assert.equal(new Date(value.startAt).getHours(), 0);
    assert.equal(new Date(value.endAt).getDate(), 2); assert.equal(new Date(value.endAt).getHours(), 0);
  });
});
