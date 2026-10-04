import { describe, expect, it, vi } from "vitest";
import { parseSportsLiveChannels } from "./liveChannels";
vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: vi.fn(),
}));
const channel = {
  atlas_channel_id: "sports-live-redzone",
  name: "NFL RedZone",
  playback_configured: true,
};
describe("live channel transport", () => {
  it("returns only public channel fields", () => {
    expect(
      parseSportsLiveChannels({
        channels: [{ ...channel, stream_url: "private" }],
      }),
    ).toEqual([
      {
        atlasChannelId: channel.atlas_channel_id,
        name: channel.name,
        playbackConfigured: true,
      },
    ]);
  });
  it.each([
    {},
    { channels: [{}] },
    { channels: [channel, channel] },
    { channels: [{ ...channel, playback_configured: "true" }] },
  ])("rejects invalid or duplicate identities", (payload) => {
    expect(() => parseSportsLiveChannels(payload)).toThrow();
  });
});
