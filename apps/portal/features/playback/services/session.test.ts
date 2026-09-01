import {
  afterEach,
  describe,
  expect,
  it,
  vi
} from "vitest";

import * as authenticated from "../../../lib/services/authenticated";
import { resolvePlaybackSession } from "./session";

afterEach(() => {
  vi.restoreAllMocks();
});


describe("subtitle selection", () => {
  it("keeps automatic subtitle behavior off the query string", async () => {
    const request = vi
      .spyOn(authenticated, "authenticatedAtlasApiRequest")
      .mockResolvedValue({
        available: true,
        action: "watch_now",
        label: "Watch Now",
        backend: "jellyfin",
        source_type: "library",
        provider: "jellyfin",
        requested_target_id: "item-1",
        playable_target_id: "item-1",
        title: "Example",
        media_type: "movie",
        duration_ticks: 100,
        can_seek: true,
        playback_bootstrap_url:
          "https://playback.shadowinc.co/_atlas/playback/bootstrap",
        playback_capability: "capability",
        audio_tracks: [],
        subtitle_tracks: [],
        previous_target_id: null,
        next_target_id: null
      });

    await resolvePlaybackSession(
      "jellyfin",
      "item-1",
      undefined,
      "auto"
    );

    expect(request.mock.calls.at(-1)?.[0]).toBe(
      "/media/playback/jellyfin/item-1/session"
    );
  });

  it.each([
    ["off", "off"],
    [2, "2"]
  ] as const)(
    "forwards subtitle selection %s",
    async (selection, expected) => {
      const request = vi
        .spyOn(authenticated, "authenticatedAtlasApiRequest")
        .mockResolvedValue({
          available: true,
          action: "watch_now",
          label: "Watch Now",
          backend: "jellyfin",
          source_type: "library",
          provider: "jellyfin",
          requested_target_id: "item-1",
          playable_target_id: "item-1",
          title: "Example",
          media_type: "movie",
          duration_ticks: 100,
          can_seek: true,
          playback_bootstrap_url:
            "https://playback.shadowinc.co/_atlas/playback/bootstrap",
          playback_capability: "capability",
          audio_tracks: [],
          subtitle_tracks: [],
          previous_target_id: null,
          next_target_id: null
        });

      await resolvePlaybackSession(
        "jellyfin",
        "item-1",
        undefined,
        selection
      );

      expect(request.mock.calls.at(-1)?.[0]).toBe(
        `/media/playback/jellyfin/item-1/session?subtitle=${expected}`
      );
    }
  );
});
