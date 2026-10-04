import { beforeEach, describe, expect, it, vi } from "vitest";
import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";
import { followSports, loadSportsFollows } from "./sports";
import { createSportsFollow } from "../types/sports";
vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: vi.fn(),
}));
const transport = {
  subscription_id: "sub-redzone",
  type: "channel",
  provider: "atlas",
  provider_id: "sports-live-nfl-redzone",
  name: "NFL RedZone",
  user_id: "user-one",
  enabled: true,
  record: false,
};
beforeEach(() => vi.resetAllMocks());
describe("channel follow transport", () => {
  it("sends a stable catalog identity without recording or caller-selected user", async () => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue(transport);
    expect((await followSports("channel", transport.provider_id)).type).toBe(
      "channel",
    );
    expect(authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/follows",
      expect.objectContaining({
        body: {
          type: "channel",
          provider: "atlas",
          provider_id: transport.provider_id,
        },
        retryPolicy: expect.objectContaining({ maxRetries: 0 }),
      }),
    );
  });
  it("loads persisted channel follows alongside existing team follows", async () => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue({
      subscriptions: [
        transport,
        {
          ...transport,
          type: "team",
          provider: "thesportsdb",
          provider_id: "team-one",
          subscription_id: "sub-team",
        },
      ],
    });
    expect((await loadSportsFollows()).map((follow) => follow.type)).toEqual([
      "channel",
      "team",
    ]);
  });
  it.each([
    { provider: "thesportsdb" },
    { provider_id: "not-a-channel" },
    { record: true },
  ])("rejects invalid channel follow identity or recording %j", (change) => {
    expect(() => createSportsFollow({ ...transport, ...change })).toThrow(
      "Invalid live channel follow",
    );
  });
});
