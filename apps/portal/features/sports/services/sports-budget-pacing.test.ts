import { afterEach, describe, expect, it, vi } from "vitest";
import { AtlasApiError } from "../../../lib/api/errors";
import { authenticatedAtlasApiRequest, type AuthenticatedAtlasApiRequestOptions } from "../../../lib/services/authenticated";
import { loadSportsEvents } from "./sports";

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: vi.fn(),
  authenticatedAtlasApiRequestWithMetadata: vi.fn(),
}));
afterEach(() => { vi.useRealTimers(); vi.resetAllMocks(); });

describe("cold league schedule pacing", () => {
  it("completes all eight date fetches within one user action", async () => {
    vi.useFakeTimers();
    let slots = 0;
    let upstream = 0;
    const dates = new Set<number>();
    vi.mocked(authenticatedAtlasApiRequest).mockImplementation(async <T>(path: string, options?: AuthenticatedAtlasApiRequestOptions): Promise<T> => {
      expect(path).toContain("league_id=4391");
      expect(options?.retryPolicy?.maxRetries).toBe(0);
      expect(options?.signal).toBeInstanceOf(AbortSignal);
      for (let day = 0; day < 8; day += 1) {
        if (dates.has(day)) continue;
        if (slots === 4) {
          slots = 0;
          throw new AtlasApiError({ status: 429, detail: "fixture", method: "GET",
            path: "/sports/events", requestId: "fixture", kind: "rate-limit", retryAfterSeconds: 10 });
        }
        slots += 1; upstream += 1; dates.add(day);
      }
      return { events: [] } as T;
    });
    const result = loadSportsEvents({}, { provider: "thesportsdb", leagueIds: ["4391"] });
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(result).resolves.toEqual([]);
    expect(upstream).toBe(8);
    expect(dates.size).toBe(8);
    expect(authenticatedAtlasApiRequest).toHaveBeenCalledTimes(2);
  });
});
