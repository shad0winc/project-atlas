// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startFollowedSportsRefresh } from "./followedSportsRefresh";
import type { SportsEvent, SportsFollow } from "../types/sports";
const saved = (
  type: SportsFollow["type"],
  providerId: string,
): SportsFollow => ({
  subscriptionId: providerId,
  provider: "thesportsdb",
  providerId,
  type,
  name: "Saved",
  userId: "owner",
  enabled: true,
  record: false,
  createdAt: null,
});
const event: SportsEvent = {
  provider: "thesportsdb",
  providerEventId: "game",
  name: "Game",
  league: "NFL",
  sport: "Football",
  startAt: "2026-10-05T00:20:00Z",
  status: "live",
  requested: false,
};
let stop: (() => void) | undefined;
beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
});
afterEach(() => {
  stop?.();
  stop = undefined;
  vi.useRealTimers();
});
const flush = async () => {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
};
describe("followed Sports refresh", () => {
  it("groups identity filters, excludes channels and disabled follows, and replaces live status with final", async () => {
    const load = vi
      .fn()
      .mockResolvedValueOnce([event])
      .mockResolvedValueOnce([{ ...event, status: "final" }]);
    const publish = vi.fn();
    stop = startFollowedSportsRefresh({
      follows: [
        saved("team", "team"),
        saved("league", "nfl"),
        saved("event", "game"),
        saved("event", "game"),
        saved("channel", "channel"),
        { ...saved("team", "disabled"), enabled: false },
      ],
      load,
      publish,
    });
    await flush();
    expect(load).toHaveBeenCalledTimes(1);
    expect(load.mock.calls[0][1]).toEqual({
      provider: "thesportsdb",
      teamIds: ["team"],
      leagueIds: ["nfl"],
      eventIds: ["game"],
    });
    expect(publish.mock.lastCall?.[1][0].value[0].status).toBe("live");
    await vi.advanceTimersByTimeAsync(60_000);
    expect(publish.mock.lastCall?.[1][0].value[0].status).toBe("final");
  });
  it("invalidates previous live data before a failing refresh and stops after cleanup", async () => {
    const load = vi
      .fn()
      .mockResolvedValueOnce([event])
      .mockRejectedValueOnce(new Error("rate limited"));
    const publish = vi.fn();
    stop = startFollowedSportsRefresh({
      follows: [saved("event", "game")],
      load,
      publish,
    });
    await flush();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(publish.mock.calls[2][1]).toBeNull();
    expect(publish.mock.lastCall?.[1][0].status).toBe("rejected");
    stop();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(load).toHaveBeenCalledTimes(2);
  });
  it("hides stale live data and prevents an aborted response from publishing", async () => {
    let resolve!: (events: readonly SportsEvent[]) => void;
    const load = vi.fn(
      () =>
        new Promise<readonly SportsEvent[]>((done) => {
          resolve = done;
        }),
    );
    const publish = vi.fn();
    stop = startFollowedSportsRefresh({
      follows: [saved("event", "game")],
      load,
      publish,
    });
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
    resolve([event]);
    await flush();
    expect(publish.mock.calls.every((call) => call[1] === null)).toBe(true);
    expect(load).toHaveBeenCalledTimes(1);
  });
});
