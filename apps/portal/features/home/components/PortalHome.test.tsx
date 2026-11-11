// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";

import { PortalHome } from "./PortalHome";
import { loadSportsFollows } from "../../sports";
import { loadCuratedCatalog, loadCuratedSchedule, type CuratedSchedule } from "../../sports/services/curatedSchedule";
import { resumeKey, writeResume } from "../../playback/services/continuity";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>
}));
vi.mock("../../../lib/authorization", async original => ({
  ...await original<typeof import("../../../lib/authorization")>(),
  usePermission: () => ({ can: (permission: string) => ["sports.read", "media.read"].includes(permission) })
}));
vi.mock("../../sports", () => ({ loadSportsFollows: vi.fn() }));
vi.mock("../../sports/services/curatedSchedule", async original => ({
  ...await original<typeof import("../../sports/services/curatedSchedule")>(),
  loadCuratedCatalog: vi.fn(), loadCuratedSchedule: vi.fn()
}));

it("resumes the exact episode and replaces a followed start time after a cache refresh", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-11-11T15:00:00Z"));
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  const fixture: CuratedSchedule = {
    competitionId: "nba", providerLeagueId: "basketball/nba",
    startAt: "2026-11-11T15:00:00Z", endAt: "2026-11-18T15:00:00Z", evaluatedAt: "2026-11-11T15:00:00Z",
    status: "ready", coverageComplete: true, observedAt: "2026-11-11T15:00:00Z", expiresAt: "2026-11-11T15:04:00Z",
    retryAfterSeconds: 0, retained: false,
    events: [{
      provider: "espn", providerEventId: "basketball-nba-401", providerLeagueId: "basketball/nba",
      homeTeamId: "basketball-nba-5", name: "Fixture matchup", sport: "Basketball", league: "NBA",
      startAt: "2026-11-12T00:00:00Z", status: "scheduled", requested: false,
      metadataObservedAt: "2026-11-11T15:00:00Z", metadataExpiresAt: "2026-11-11T15:04:00Z"
    }]
  };
  vi.mocked(loadSportsFollows).mockResolvedValue([{
    provider: "espn", providerId: "basketball-nba-5", type: "team", enabled: true,
    name: "Fixture", userId: "viewer", subscriptionId: "fixture", record: false, createdAt: null
  }]);
  vi.mocked(loadCuratedCatalog).mockResolvedValue({
    enabled: true,
    competitions: [
      { id: "nba", sport: "Basketball", name: "NBA", provider: "espn", providerLeagueId: "basketball/nba",
        status: "configured", teamDirectorySupported: true },
      { id: "nhl", sport: "Hockey", name: "NHL", provider: "espn", providerLeagueId: "hockey/nhl",
        status: "configured", teamDirectorySupported: true }
    ]
  });
  const moved = "2026-11-12T01:00:00Z";
  vi.mocked(loadCuratedSchedule).mockResolvedValueOnce(fixture)
    .mockResolvedValueOnce({ ...fixture, events: fixture.events.map(event => ({ ...event, startAt: moved })) })
    .mockRejectedValue(new Error("Cache unavailable"));

  const key = resumeKey("viewer", "jellyfin", "episode-2", true);
  writeResume(window.localStorage, key, 128, false, { title: "Episode two", duration: 300, episode: true });
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  try {
    await act(async () => root.render(<PortalHome userId="viewer" />));
    await act(async () => vi.advanceTimersByTimeAsync(0));
    expect(container.querySelector('a[href="/portal/theater?provider=jellyfin&item=episode-2"]')?.textContent).toBe("Resume episode");
    expect(container.textContent).toContain("2:08 watched");
    expect(loadCuratedSchedule).toHaveBeenCalledTimes(1);
    expect(loadCuratedSchedule).toHaveBeenCalledWith("nba", "week", expect.any(AbortSignal));
    expect(container.querySelector("time")?.dateTime).toBe(fixture.events[0].startAt);
    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(container.querySelector("time")?.dateTime).toBe(moved);
    await act(async () => vi.advanceTimersByTimeAsync(60_000));
    expect(container.textContent).toContain("Last known time");
    expect(container.querySelector("time")?.dateTime).toBe(moved);
  } finally {
    await act(async () => root.unmount());
    container.remove();
    window.localStorage.clear();
    vi.useRealTimers();
  }
});
