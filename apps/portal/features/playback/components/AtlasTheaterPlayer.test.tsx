import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AtlasTheaterPlayer } from "./AtlasTheaterPlayer";
import type { PlaybackSession } from "../types/session";

describe("AtlasTheaterPlayer", () => {
  it("supports an injectable session resolver for non-generic playback", () => {
    const playerSource = readFileSync(
      new URL("./AtlasTheaterPlayer.tsx", import.meta.url),
      "utf8"
    );

    expect(playerSource).toContain(
      "sessionResolver = resolvePlaybackSession"
    );

    expect(playerSource).toContain(
      "sessionResolver?:"
    );

    expect(playerSource).toContain(
      "const refreshed = await sessionResolver("
    );

    expect(playerSource).not.toContain(
      "const refreshed = await resolvePlaybackSession("
    );
  });

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

  it("renders available closed-caption tracks", () => {
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
      subtitleTracks: [
        Object.freeze({
          index: 2,
          kind: "subtitle",
          label: "English",
          language: "eng",
          codec: "srt",
          default: true,
          forced: false
        }),
        Object.freeze({
          index: 3,
          kind: "subtitle",
          label: "English Signs",
          language: "eng",
          codec: "srt",
          default: false,
          forced: true
        })
      ]
    });

    const markup = renderToStaticMarkup(
      <AtlasTheaterPlayer session={session} />
    );

    expect(markup).toContain("Closed captions");
    expect(markup).toContain(">Auto<");
    expect(markup).toContain(">Off<");
    expect(markup).toContain("English (Default)");
    expect(markup).toContain("English Signs (Forced)");

    expect(markup).not.toContain(
      "sensitive-atlas-capability"
    );
    expect(markup).not.toContain("ApiKey");
    expect(markup).not.toContain("X-Emby-Token");
  });

});

describe("AtlasTheaterPlayer active-item retention lifecycle", () => {
  const activeMovieSession: PlaybackSession = Object.freeze({
    available: true,
    action: "watch_now",
    label: "Watch Now",
    backend: "jellyfin",
    sourceType: "library",
    provider: "jellyfin",
    requestedTargetId: "movie-123",
    playableTargetId: "movie-123",
    title: "Example Movie",
    mediaType: "movie",
    canSeek: true,
    playbackBootstrapUrl:
      "https://playback.shadowinc.co/_atlas/playback/bootstrap",
    playbackCapability: "sensitive-atlas-capability",
    audioTracks: [],
    subtitleTracks: []
  });

  it("renders authoritative retention for the active playback item", () => {
    const authoritativeDeleteAt =
      "2031-02-03T04:05:06Z";

    const markup = renderToStaticMarkup(
      <AtlasTheaterPlayer
        retention={{
          provider: "jellyfin",
          itemId: "movie-123",
          eligible: false,
          retained: true,
          lifecycle: {
            state: "scheduled",
            rule: "watched_72h",
            basisAt: "2031-01-31T04:05:06Z",
            deleteAt: authoritativeDeleteAt
          }
        }}
        session={activeMovieSession}
      />
    );

    expect(markup).toContain("Scheduled for deletion");
    expect(markup).toContain(authoritativeDeleteAt);
    expect(markup).toContain(
      `dateTime="${authoritativeDeleteAt}"`
    );

    expect(markup).not.toContain(
      "sensitive-atlas-capability"
    );
  });

  it("renders Favorite only when active-item Favorite mutation is authorized", () => {
    const authorizedMarkup = renderToStaticMarkup(
      <AtlasTheaterPlayer
        canFavorite
        favoriteState="idle"
        onFavorite={() => undefined}
        session={activeMovieSession}
      />
    );

    expect(authorizedMarkup).toContain(
      "Add Example Movie to favorites"
    );

    const unauthorizedMarkup = renderToStaticMarkup(
      <AtlasTheaterPlayer
        canFavorite={false}
        favoriteState="idle"
        onFavorite={() => undefined}
        session={activeMovieSession}
      />
    );

    expect(unauthorizedMarkup).not.toContain(
      "Add Example Movie to favorites"
    );
  });
});
