import { beforeEach, describe, expect, it, vi } from "vitest";
import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";
import { followSports, searchSports } from "./sports";
vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: vi.fn(),
  authenticatedAtlasApiRequestWithMetadata: vi.fn(),
}));
beforeEach(() => vi.resetAllMocks());
const transport = {
  subscription_id: "sub-secondary", type: "league", provider: "espn",
  provider_id: "nfl", name: "NFL", user_id: "owner", enabled: true, record: false,
};
describe("Sports provider identity transport", () => {
  it("retains the requested provider on team and league results", async () => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue({
      results: [{ id: "nfl", name: "NFL", sport: "Football" }],
    });
    const results = await searchSports("league", "NFL", { provider: "espn" });
    expect(authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/search/leagues?provider=espn&query=NFL", expect.anything(),
    );
    expect(results[0]).toMatchObject({ id: "nfl", provider: "espn" });
  });

  it("keeps the legacy search provider explicit in parsed results", async () => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue({
      results: [{ id: "4391", name: "NFL" }],
    });
    expect((await searchSports("league", "NFL"))[0]).toMatchObject({ provider: "thesportsdb" });
  });

  it("sends the selected provider when saving a follow", async () => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue(transport);
    await followSports("league", "nfl", { provider: "espn" });
    expect(authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/follows", expect.objectContaining({
        body: { type: "league", provider: "espn", provider_id: "nfl" },
      }),
    );
  });

  it("keeps event recording's prerequisite follow under its source provider", async () => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue({
      ...transport, type: "event", provider_id: "401872996",
    });
    await followSports("event", "401872996", { provider: "espn" });
    expect(authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/follows", expect.objectContaining({
        body: { type: "event", provider: "espn", provider_id: "401872996" },
      }),
    );
  });

  it("keeps channel follows owned by Atlas", async () => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue({
      ...transport, type: "channel", provider: "atlas", provider_id: "sports-live-nfl-redzone",
    });
    await followSports("channel", "sports-live-nfl-redzone", { provider: "espn" });
    expect(authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/follows", expect.objectContaining({
        body: { type: "channel", provider: "atlas", provider_id: "sports-live-nfl-redzone" },
      }),
    );
  });

  it("rejects an explicitly empty provider before saving", async () => {
    await expect(followSports("league", "nfl", { provider: " " })).rejects.toThrow(
      "sportsFollow.provider must not be empty.",
    );
    expect(authenticatedAtlasApiRequest).not.toHaveBeenCalled();
  });
});
