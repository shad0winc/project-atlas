import { describe, expect, it } from "vitest";

import { createPlaybackAction } from "./playback";

describe("createPlaybackAction", () => {
  it("normalizes the provider-neutral Jellyfin action", () => {
    expect(
      createPlaybackAction({
        available: true,
        action: "watch_now",
        label: "Watch Now",
        backend: "JELLYFIN",
        sourceType: "library",
        provider: "JELLYFIN",
        targetId: " item-1 ",
        href: "/jellyfin/web/index.html#!/details?id=item-1"
      })
    ).toEqual({
      available: true,
      action: "watch_now",
      label: "Watch Now",
      backend: "jellyfin",
      sourceType: "library",
      provider: "jellyfin",
      targetId: "item-1",
      href: "/jellyfin/web/index.html#!/details?id=item-1"
    });
  });
});
