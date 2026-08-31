import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AtlasTheaterPlayer } from "./AtlasTheaterPlayer";
import type { PlaybackSession } from "../types/session";

describe("AtlasTheaterPlayer", () => {
  it("renders Atlas controls without rendering playback credentials", () => {
    const session: PlaybackSession = Object.freeze({
      available: true,
      action: "watch_now",
      label: "Watch Now",
      backend: "jellyfin",
      sourceType: "library",
      provider: "jellyfin",
      requestedTargetId: "series-1",
      playableTargetId: "episode-1",
      title: "Example Episode",
      mediaType: "tv",
      canSeek: true,
      playbackBootstrapUrl:
        "https://playback.shadowinc.co/_atlas/playback/bootstrap",
      playbackCapability: "sensitive-atlas-capability",
      audioTracks: [],
      subtitleTracks: []
    });

    const markup = renderToStaticMarkup(
      <AtlasTheaterPlayer session={session} />
    );

    expect(markup).toContain("<video");
    expect(markup).toContain("controls");
    expect(markup).toContain("playsInline");
    expect(markup).toContain("Atlas embedded player");
    expect(markup).toContain("Powered by Jellyfin");
    expect(markup).not.toContain("sensitive-atlas-capability");
    expect(markup).not.toContain("ApiKey");
    expect(markup).not.toContain("X-Emby-Token");
  });
});
