import { beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ request: vi.fn(), authenticated: vi.fn(), metadata: vi.fn() }));
vi.mock("../../../lib/api/client", () => ({ atlasApiRequest: mocks.request }));
vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: mocks.authenticated,
  authenticatedAtlasApiRequestWithMetadata: mocks.metadata
}));
import { createSportsLiveSession, releaseSportsLiveSession } from "./sports";
beforeEach(() => vi.resetAllMocks());
it("uses only the in-memory cleanup capability when login is unavailable", async () => {
  mocks.authenticated.mockRejectedValue(new Error("Login unavailable"));
  await releaseSportsLiveSession("owned-session", { releaseCapability: "cleanup-only" });
  expect(mocks.authenticated).not.toHaveBeenCalled();
  expect(mocks.request).toHaveBeenCalledWith("/sports/live/sessions/owned-session/release-capability",
    expect.objectContaining({ method: "DELETE", retryAuthentication: false,
      headers: { "X-Atlas-Live-Release-Capability": "cleanup-only" } }));
  expect(mocks.request.mock.calls[0][1]).not.toHaveProperty("accessToken");
});
it("preserves compatibility with sessions opened before this release", async () => {
  await releaseSportsLiveSession("legacy-session");
  expect(mocks.authenticated).toHaveBeenCalled();
  expect(mocks.request).not.toHaveBeenCalled();
});
it("does not retry uncertain cleanup through another authorization path", async () => {
  mocks.request.mockRejectedValue(new Error("Cleanup requires reconciliation"));
  await expect(releaseSportsLiveSession("owned-session", { releaseCapability: "cleanup-only" })).rejects.toThrow();
  expect(mocks.request).toHaveBeenCalledTimes(1);
  expect(mocks.authenticated).not.toHaveBeenCalled();
});

function openResponse(ttl = "90") {
  return { data: { action: "watch_live", source_type: "live", available: true,
    label: "Watch live", backend: "jellyfin", provider: "jellyfin", requested_target_id: "channel",
    playable_target_id: "item", title: "Channel", media_type: "Video", duration_ticks: null,
    can_seek: false, playback_bootstrap_url: "/bootstrap", playback_capability: "play-only",
    audio_tracks: [], subtitle_tracks: [], previous_target_id: null, next_target_id: null },
    headers: new Headers({ "X-Atlas-Live-Session-ID": "owned-session", "X-Atlas-Live-Session-TTL": ttl,
      "X-Atlas-Live-Release-Capability": "cleanup-only" }) };
}
it("retains the response credential for that exact opened session", async () => {
  mocks.metadata.mockResolvedValue(openResponse());
  const result = await createSportsLiveSession("channel");
  expect(result.releaseCapability).toBe("cleanup-only");
  expect(result.session.playbackCapability).toBe("play-only");
});
it("uses scoped cleanup when validation fails after admission", async () => {
  mocks.metadata.mockResolvedValue(openResponse("bad"));
  await expect(createSportsLiveSession("channel")).rejects.toThrow("valid TTL");
  expect(mocks.request).toHaveBeenCalledWith("/sports/live/sessions/owned-session/release-capability",
    expect.objectContaining({ headers: { "X-Atlas-Live-Release-Capability": "cleanup-only" } }));
  expect(mocks.authenticated).not.toHaveBeenCalled();
});
