import { afterEach, describe, expect, it, vi } from "vitest";

import { bootstrapPlaybackStream } from "./stream";
import type { PlaybackSession } from "../types/session";

const session: PlaybackSession = Object.freeze({
  available: true,
  action: "watch_now",
  label: "Watch Now",
  backend: "jellyfin",
  sourceType: "library",
  provider: "jellyfin",
  requestedTargetId: "series-1",
  playableTargetId: "episode-1",
  title: "Example",
  mediaType: "tv",
  canSeek: true,
  playbackBootstrapUrl:
    "https://playback.shadowinc.co/_atlas/playback/bootstrap",
  playbackCapability: "atlas-capability",
  audioTracks: [],
  subtitleTracks: []
});

describe("playback stream bootstrap", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("exchanges the Atlas capability without exposing Jellyfin auth", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          stream_url:
            "https://playback.shadowinc.co/videos/episode-1/master.m3u8?MediaSourceId=source-1"
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await bootstrapPlaybackStream(session);

    expect(fetchMock).toHaveBeenCalledWith(
      new URL(session.playbackBootstrapUrl),
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        credentials: "include",
        headers: expect.objectContaining({
          Authorization: "Bearer atlas-capability"
        })
      })
    );

    expect(result.streamUrl).toBe(
      "https://playback.shadowinc.co/videos/episode-1/master.m3u8?MediaSourceId=source-1"
    );
    expect(result.streamUrl).not.toContain("ApiKey");
  });

  it("rejects an untrusted bootstrap origin", async () => {
    await expect(
      bootstrapPlaybackStream({
        ...session,
        playbackBootstrapUrl:
          "https://evil.example/_atlas/playback/bootstrap"
      })
    ).rejects.toThrow("Playback bootstrap endpoint is not trusted.");
  });

  it("rejects stream URLs carrying authentication material", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            stream_url:
              "https://playback.shadowinc.co/videos/episode-1/master.m3u8?ApiKey=secret"
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" }
          }
        )
      )
    );

    await expect(
      bootstrapPlaybackStream(session)
    ).rejects.toThrow(
      "Playback stream exposed authentication material."
    );
  });
});
