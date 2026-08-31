import { beforeEach, describe, expect, it, vi } from "vitest";

import { resolvePlaybackAction } from "./playback";

const { authenticatedRequestMock } = vi.hoisted(() => ({
  authenticatedRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedRequestMock
}));

describe("playback authenticated service boundary", () => {
  beforeEach(() => {
    authenticatedRequestMock.mockReset();
  });

  it("resolves the exact authenticated Jellyfin media identity", async () => {
    authenticatedRequestMock.mockResolvedValue({
      available: true,
      action: "watch_now",
      label: "Watch Now",
      backend: "jellyfin",
      source_type: "library",
      provider: "jellyfin",
      target_id: "item-123",
      href: "https://playback.example/item-123"
    });

    const action = await resolvePlaybackAction(
      "JELLYFIN",
      " item-123 "
    );

    expect(authenticatedRequestMock).toHaveBeenCalledWith(
      "/media/playback/jellyfin/item-123",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );

    expect(action.provider).toBe("jellyfin");
    expect(action.targetId).toBe("item-123");
    expect(action.href).toBe("https://playback.example/item-123");
  });

  it("rejects a response that crosses the requested media identity", async () => {
    authenticatedRequestMock.mockResolvedValue({
      available: true,
      action: "watch_now",
      label: "Watch Now",
      backend: "jellyfin",
      source_type: "library",
      provider: "jellyfin",
      target_id: "different-item",
      href: "https://playback.example/different-item"
    });

    await expect(
      resolvePlaybackAction("jellyfin", "item-123")
    ).rejects.toThrow(
      "Playback response did not match the requested media identity."
    );
  });
});
