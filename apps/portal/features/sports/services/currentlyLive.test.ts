import { describe, expect, it } from "vitest";
import { followedLiveEvents, sportsLocalStart } from "./currentlyLive";
import type { SportsEvent, SportsFollow } from "../types/sports";
const event: SportsEvent = {
  provider: "thesportsdb",
  providerEventId: "game",
  name: "Lions vs Panthers",
  sport: "Football",
  league: "NFL",
  startAt: "2026-10-05T00:20:00Z",
  status: "live",
  requested: false,
  homeTeamId: "lions",
  awayTeamId: "panthers",
  providerLeagueId: "nfl",
};
const follow = (
  type: SportsFollow["type"],
  providerId: string,
): SportsFollow => ({
  type,
  providerId,
  provider: "thesportsdb",
  subscriptionId: `${type}:${providerId}`,
  userId: "owner",
  name: "Saved",
  enabled: true,
  record: false,
  createdAt: null,
});
const now = Date.parse("2026-10-05T01:00:00Z");
describe("Currently Live", () => {
  it("matches stable event, team and league IDs and deduplicates overlaps", () => {
    for (const saved of [
      follow("event", "game"),
      follow("team", "panthers"),
      follow("league", "nfl"),
    ])
      expect(followedLiveEvents([event], [saved], now)).toEqual([event]);
    expect(
      followedLiveEvents(
        [event, event],
        [follow("team", "lions"), follow("event", "game")],
        now,
      ),
    ).toEqual([event]);
  });
  it("excludes ended, scheduled, future and invalid-time events", () => {
    for (const changed of [
      { status: "finished" },
      { status: "scheduled" },
      { startAt: "2027-01-01T00:00:00Z" },
      { startAt: "invalid" },
    ])
      expect(
        followedLiveEvents(
          [{ ...event, ...changed }],
          [follow("event", "game")],
          now,
        ),
      ).toEqual([]);
  });
  it("does not match names, disabled follows, another provider or unverified channels", () => {
    expect(
      followedLiveEvents(
        [event],
        [
          follow("team", "Lions"),
          follow("channel", "sports-live-game"),
          { ...follow("event", "game"), enabled: false },
          { ...follow("event", "game"), provider: "other" },
        ],
        now,
      ),
    ).toEqual([]);
  });
  it("formats a local date and time with a timezone and handles missing times", () => {
    expect(sportsLocalStart(event.startAt)).toMatch(/2026/);
    expect(sportsLocalStart("invalid")).toBe("Start time unavailable");
  });
});
