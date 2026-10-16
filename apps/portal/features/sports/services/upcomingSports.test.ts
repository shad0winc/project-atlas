import { describe, expect, it } from "vitest";
import type { SportsEvent } from "../types/sports";
import { upcomingSportsEvents } from "./upcomingSports";

const now = Date.parse("2026-10-15T23:00:00Z");
const game = (id: string, startAt: string, status = "scheduled"): SportsEvent => ({
  provider: "thesportsdb",
  providerEventId: id,
  name: id,
  sport: "American Football",
  league: "NFL",
  startAt,
  status,
  requested: false,
});

describe("seven-day upcoming Sports window", () => {
  it("includes the entire returned Sunday slate without a display limit", () => {
    const games = Array.from({ length: 14 }, (_, index) =>
      game(`sunday-${index}`, "2026-10-18T17:00:00Z"),
    );
    expect(upcomingSportsEvents(games, now)).toHaveLength(14);
  });

  it("bounds actual instants across timezone offsets and excludes live/final data", () => {
    const result = upcomingSportsEvents([
      game("past", "2026-10-15T22:59:59Z"),
      game("start", "2026-10-15T19:00:00-04:00"),
      game("end", "2026-10-22T23:00:00Z"),
      game("beyond", "2026-10-22T23:00:01Z"),
      game("invalid", "unknown"),
      game("live", "2026-10-16T23:00:00Z", "live"),
      game("final", "2026-10-16T23:00:00Z", "final"),
    ], now);
    expect(result.map((event) => event.providerEventId)).toEqual(["start", "end"]);
  });

  it("replaces rescheduled records before filtering and preserves provider identity", () => {
    const initial = game("same", "2026-10-16T23:00:00Z");
    const moved = { ...initial, startAt: "2026-11-01T23:00:00Z" };
    const other = { ...initial, provider: "other" };
    expect(upcomingSportsEvents([initial, moved, other], now)).toEqual([other]);
    expect(upcomingSportsEvents([initial, { ...initial, status: "final" }], now)).toEqual([]);
  });

  it("sorts without mutating inputs and drops elapsed occurrences on refresh", () => {
    const first = game("first", "2026-10-16T01:00:00Z");
    const last = game("last", "2026-10-20T01:00:00Z");
    const input = Object.freeze([last, first]);
    expect(upcomingSportsEvents(input, now)).toEqual([first, last]);
    expect(input).toEqual([last, first]);
    expect(upcomingSportsEvents(input, Date.parse("2026-10-17T00:00:00Z"))).toEqual([last]);
  });
});
