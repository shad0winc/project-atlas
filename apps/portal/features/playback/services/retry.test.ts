import assert from "node:assert/strict";
import { describe, it } from "vitest";
import type { PlaybackSession } from "../types/session";
import { refreshPlaybackForRetry, retryResumePosition } from "./retry";
import { bootstrapPlaybackStream } from "./stream";

const session: PlaybackSession = {
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
  playbackBootstrapUrl: "https://playback.shadowinc.co/_atlas/playback/bootstrap",
  playbackCapability: "expired-capability",
  audioTracks: [],
  subtitleTracks: []
};

describe("playback retry renewal", () => {
  it("retries an expired bootstrap with fresh authorization", async () => {
    const originalFetch = globalThis.fetch;
    const authorizations: string[] = [];
    globalThis.fetch = async (_input, init) => {
      const authorization = new Headers(init?.headers).get("Authorization") ?? "";
      authorizations.push(authorization);
      assert.equal(init?.credentials, "include");
      return authorization === "Bearer expired-capability"
        ? new Response(null, { status: 401 })
        : Response.json({
            stream_url: "https://playback.shadowinc.co/videos/episode-1/master.m3u8"
          });
    };
    try {
      await assert.rejects(bootstrapPlaybackStream(session), /authorization expired/);
      const renewed = await refreshPlaybackForRetry(
        session,
        async () => ({
          ...session,
          playbackCapability: "fresh-capability"
        }),
        "auto",
        new AbortController().signal
      );
      const stream = await bootstrapPlaybackStream(renewed);
      assert.equal(stream.streamUrl, "https://playback.shadowinc.co/videos/episode-1/master.m3u8");
      assert.deepEqual(authorizations, ["Bearer expired-capability", "Bearer fresh-capability"]);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("obtains a fresh capability for the current episode and selected subtitles", async () => {
    const controller = new AbortController();
    const refreshed = await refreshPlaybackForRetry(
      session,
      async (...args) => {
        assert.deepEqual(args, ["jellyfin", "episode-1", controller.signal, 2]);
        return { ...session, playbackCapability: "fresh-capability" };
      },
      2,
      controller.signal
    );
    assert.equal(refreshed.playbackCapability, "fresh-capability");
    assert.notEqual(refreshed, session);
    assert.equal(session.playbackCapability, "expired-capability");
  });

  it("uses the injected live resolver rather than a generic library request", async () => {
    const live = { ...session, sourceType: "live" as const, canSeek: false };
    let calls = 0;
    await refreshPlaybackForRetry(
      live,
      async (_, item, __, subtitle) => {
        calls += 1;
        assert.equal(item, live.playableTargetId);
        assert.equal(subtitle, "off");
        return { ...live, playbackCapability: "fresh-live-capability" };
      },
      "off",
      new AbortController().signal
    );
    assert.equal(calls, 1);
  });

  it("propagates renewal failure without returning the expired session", async () => {
    await assert.rejects(
      refreshPlaybackForRetry(
        session,
        async () => {
          throw new Error("renewal denied");
        },
        "auto",
        new AbortController().signal
      ),
      /renewal denied/
    );
  });

  it("rejects unavailable or empty-capability responses", async () => {
    for (const response of [
      { ...session, available: false },
      { ...session, playbackCapability: " " }
    ]) {
      await assert.rejects(
        refreshPlaybackForRetry(
          session,
          async () => response,
          "auto",
          new AbortController().signal
        ),
        /not currently available/
      );
    }
  });

  it("does not start a request after cancellation", async () => {
    const controller = new AbortController();
    controller.abort();
    let calls = 0;
    await assert.rejects(
      refreshPlaybackForRetry(
        session,
        async () => {
          calls += 1;
          return session;
        },
        "auto",
        controller.signal
      ),
      { name: "AbortError" }
    );
    assert.equal(calls, 0);
  });

  it("rejects a late response after cancellation", async () => {
    const controller = new AbortController();
    await assert.rejects(
      refreshPlaybackForRetry(
        session,
        async () => {
          controller.abort();
          return { ...session, playbackCapability: "fresh" };
        },
        "auto",
        controller.signal
      ),
      { name: "AbortError" }
    );
  });

  it("preserves the position captured before a failed player resets to zero", () => {
    assert.equal(retryResumePosition(true, 542, null), 542);
    assert.equal(retryResumePosition(true, 0, 542), 542);
    assert.equal(retryResumePosition(true, NaN, 542), 542);
    assert.equal(retryResumePosition(true, undefined, 542), 542);
  });

  it("does not seek live streams or restore invalid positions", () => {
    assert.equal(retryResumePosition(false, 542, 542), null);
    assert.equal(retryResumePosition(true, -1, NaN), null);
    assert.equal(retryResumePosition(true, 0, null), null);
  });
});
