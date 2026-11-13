// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SportsScheduleBrowser } from "./SportsScheduleBrowser";
import { loadCuratedCatalog, loadCuratedSchedule, loadCuratedTeams, type CuratedSchedule } from "../services/curatedSchedule";
import type { SportsFollow } from "../types/sports";
import { loadSportsLiveAvailability } from "../services/sports";

vi.mock("../services/curatedSchedule", async original => ({ ...await original<typeof import("../services/curatedSchedule")>(),
  loadCuratedCatalog: vi.fn(), loadCuratedSchedule: vi.fn(), loadCuratedTeams: vi.fn() }));
vi.mock("../services/sports", () => ({ loadSportsLiveAvailability: vi.fn() }));
let root: Root;
let container: HTMLDivElement;
const onFollow = vi.fn(async () => {});
const onRequestEvent = vi.fn(async () => {});
const onWatchLive = vi.fn(async () => {});
const onScheduleChanged = vi.fn();
const snapshot: CuratedSchedule = { competitionId: "nba", providerLeagueId: "basketball/nba",
  startAt: "2026-10-31T04:00:00Z", endAt: "2026-11-01T04:00:00Z", evaluatedAt: "2026-11-01T00:12:00Z",
  status: "ready", coverageComplete: true, observedAt: "2026-11-01T00:10:00Z", expiresAt: "2026-11-01T00:15:00Z",
  retryAfterSeconds: 0, retained: false, events: [{ provider: "espn", providerEventId: "basketball-nba-401909900",
    providerLeagueId: "basketball/nba", name: "Cavaliers at Bucks", sport: "Basketball", league: "NBA",
    startAt: "2026-11-01T00:00:00Z", status: "live", requested: false,
    awayTeamId: "basketball-nba-5", homeTeamId: "basketball-nba-15",
    metadataObservedAt: "2026-11-01T00:10:00Z", metadataExpiresAt: "2026-11-01T00:15:00Z" }] };

const eventFollow: SportsFollow = {
  subscriptionId: "follow-game", provider: "espn", type: "event", providerId: snapshot.events[0].providerEventId,
  enabled: true, record: false, name: snapshot.events[0].name, userId: "viewer", createdAt: null,
};

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers(); vi.setSystemTime(new Date("2026-11-01T00:12:00Z"));
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  vi.mocked(loadCuratedCatalog).mockResolvedValue({ enabled: true, competitions: [{ id: "nba", sport: "Basketball", name: "NBA",
    provider: "espn", providerLeagueId: "basketball/nba", teamDirectorySupported: true, status: "configured" }] });
  vi.mocked(loadCuratedTeams).mockResolvedValue({ competitionId: "nba", status: "ready", teams: [
    { id: "basketball-nba-5", name: "Cleveland Cavaliers" }, { id: "basketball-nba-15", name: "Milwaukee Bucks" }] });
  vi.mocked(loadCuratedSchedule).mockResolvedValue(snapshot);
  vi.mocked(loadSportsLiveAvailability).mockResolvedValue({ available: false, atlasChannelId: null });
  container = document.createElement("div"); document.body.append(container); root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount()); container.remove(); vi.useRealTimers(); vi.resetAllMocks();
});
async function mount(follows: readonly SportsFollow[] = []) {
  await act(async () => root.render(<SportsScheduleBrowser follows={follows} onFollow={onFollow}
    onRequestEvent={onRequestEvent} onWatchLive={onWatchLive} onScheduleChanged={onScheduleChanged} />));
}
async function click(label: string) {
  const button = [...container.querySelectorAll("button")].find(item => item.textContent === label);
  expect(button).toBeDefined(); await act(async () => button!.click());
}
describe("curated schedule actions and cache refresh", () => {
  it("follows either participant with its exact ESPN identity", async () => {
    await mount(); await click("Follow Cleveland Cavaliers"); await click("Follow Milwaukee Bucks");
    expect(onFollow).toHaveBeenCalledWith("team", "basketball-nba-5", "espn");
    expect(onFollow).toHaveBeenCalledWith("team", "basketball-nba-15", "espn");
  });
  it("follows the selected event without changing its provider", async () => {
    await mount(); await click("Follow event");
    expect(onRequestEvent).toHaveBeenCalledWith({ provider: "espn", providerEventId: "basketball-nba-401909900" });
  });
  it("explains the follow requirement and waits for a feed after following", async () => {
    await mount();
    expect(container.textContent).toContain("Follow an event, either team, or the competition");
    expect([...container.querySelectorAll("button")].map(button => button.textContent)).not.toContain("Watch Live");
    expect(loadSportsLiveAvailability).not.toHaveBeenCalled();
    await mount([eventFollow]);
    expect(loadSportsLiveAvailability).toHaveBeenCalledWith("espn", eventFollow.providerId, { signal: expect.any(AbortSignal) });
    expect(onWatchLive).not.toHaveBeenCalled();
    expect(container.textContent).toContain("Waiting for a live feed.");
    expect([...container.querySelectorAll("button")].map(button => button.textContent)).not.toContain("Watch Live");
  });
  it.each([
    eventFollow,
    { ...eventFollow, type: "team", providerId: "basketball-nba-5" } as const,
    { ...eventFollow, type: "team", providerId: "basketball-nba-15" } as const,
    { ...eventFollow, type: "league", providerId: "basketball/nba" } as const,
  ])("opens the verified channel for a $type follow on $providerId", async follow => {
    vi.mocked(loadSportsLiveAvailability).mockResolvedValue({ available: true, atlasChannelId: "sports-live-fixture" });
    await mount([follow]); await click("Watch Live");
    expect(onWatchLive).toHaveBeenCalledWith("sports-live-fixture");
    await mount([{ ...follow, enabled: false }]);
    expect([...container.querySelectorAll("button")].map(button => button.textContent)).not.toContain("Watch Live");
  });
  it("offers verified pregame playback when the event enters the 60-minute window", async () => {
    vi.mocked(loadCuratedSchedule).mockResolvedValue({ ...snapshot, events: snapshot.events.map(item => ({
      ...item, startAt: "2026-11-01T01:12:30Z", status: "scheduled"
    })) });
    vi.mocked(loadSportsLiveAvailability).mockResolvedValue({ available: true, atlasChannelId: "sports-live-fixture" });
    await mount([eventFollow]);
    expect(loadSportsLiveAvailability).not.toHaveBeenCalled();
    expect([...container.querySelectorAll("button")].map(button => button.textContent)).not.toContain("Watch Live");
    await act(async () => vi.advanceTimersByTimeAsync(30_000));
    expect(container.textContent).toContain("Watch Live");
    vi.mocked(loadSportsLiveAvailability).mockResolvedValue({ available: false, atlasChannelId: null });
    await click("Watch Live");
    expect(onWatchLive).not.toHaveBeenCalled();
    expect(container.textContent).toContain("Atlas has no available channel for this event yet.");
  });

  it("keeps verified playback visible across a schedule cache refresh", async () => {
    const pendingPoll = new Promise<never>(() => {});
    vi.mocked(loadSportsLiveAvailability).mockResolvedValueOnce({
      available: true, atlasChannelId: "sports-live-fixture"
    }).mockImplementation(() => pendingPoll);
    const updated = { ...snapshot, events: snapshot.events.map(item => ({ ...item })) };
    vi.mocked(loadCuratedSchedule).mockResolvedValueOnce(snapshot).mockResolvedValue(updated);
    await mount([eventFollow]);
    expect(container.textContent).toContain("Watch Live");
    // The first 30-second availability poll succeeds, the next stays pending.
    vi.mocked(loadSportsLiveAvailability).mockResolvedValueOnce({ available: true, atlasChannelId: "sports-live-fixture" });
    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(loadCuratedSchedule).toHaveBeenCalledTimes(4);
    expect(container.textContent).toContain("Watch Live");
    expect(loadSportsLiveAvailability).toHaveBeenCalledTimes(3);
  });

  it("does not offer a live action for expired status", async () => {
    vi.mocked(loadCuratedSchedule).mockResolvedValue({ ...snapshot, events: snapshot.events.map(item => ({ ...item, metadataExpiresAt: "2026-11-01T00:11:00Z" })) });
    await mount(); expect(container.textContent).toContain("status needs refresh");
    expect([...container.querySelectorAll("button")].map(button => button.textContent)).not.toContain("Watch Live");
  });
  it("loads followed NBA events independently of the selected NFL schedule", async () => {
    const nba = { id: "nba", sport: "Basketball", name: "NBA", provider: "espn" as const,
      providerLeagueId: "basketball/nba", teamDirectorySupported: true, status: "configured" as const };
    vi.mocked(loadCuratedCatalog).mockResolvedValue({ enabled: true, competitions: [
      { ...nba, id: "nfl", sport: "Football", name: "NFL", providerLeagueId: "football/nfl" }, nba
    ] });
    vi.mocked(loadCuratedSchedule).mockImplementation(async id => id === "nba" ? snapshot :
      { ...snapshot, competitionId: "nfl", providerLeagueId: "football/nfl", events: [] });
    const event = snapshot.events[0];
    await mount([{ subscriptionId: "follow-nba", provider: "espn", type: "event", providerId: event.providerEventId,
      enabled: true, record: false, name: event.name, userId: "viewer", createdAt: null }]);
    expect(container.textContent).not.toContain(event.name);
    expect(loadCuratedSchedule).toHaveBeenCalledWith("nba", "today", expect.any(AbortSignal));
    expect(onScheduleChanged).toHaveBeenLastCalledWith([event]);
  });

  it("refreshes cache reads on a visible page without a click", async () => {
    await mount(); expect(loadCuratedSchedule).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(60_000)); expect(loadCuratedSchedule).toHaveBeenCalledTimes(2);
    expect(onScheduleChanged).toHaveBeenCalledWith([]);
    expect(container.textContent).toContain("Recording is unavailable");
  });
});
