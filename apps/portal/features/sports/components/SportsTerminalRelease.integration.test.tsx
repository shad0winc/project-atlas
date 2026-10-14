// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { PlaybackSession } from "../../playback/types/session";
import type { SportsLiveSessionResult } from "../services/sports";
import { SportsPageClient } from "../../../app/(protected)/portal/sports/SportsPageClient";

const mock = vi.hoisted(() => ({
  create: vi.fn(), heartbeat: vi.fn(), release: vi.fn(),
  players: [] as Array<{
    session: PlaybackSession;
    onTerminalError: (session: PlaybackSession) => void;
  }>,
}));
vi.mock("../services/sports", () => ({
  createSportsLiveSession: mock.create,
  releaseSportsLiveSession: mock.release,
}));
vi.mock("..", () => ({
  heartbeatSportsLiveSession: mock.heartbeat,
  releaseSportsLiveSession: mock.release,
  loadSportsEvents: async () => [], loadSportsFollows: async () => [],
  loadSportsLiveAvailability: async () => ({}),
  followSports: vi.fn(), requestSportsEvent: vi.fn(), searchSports: vi.fn(),
  unfollowSports: vi.fn(), updateSportsRecordingIntent: vi.fn(),
  SportsRequestView: ({ onWatchLive }: { onWatchLive: (id: string) => Promise<void> }) =>
    <button onClick={() => { void onWatchLive("fixture-channel"); }}>Watch fixture</button>,
}));
vi.mock("../../../components/portal/PortalPage", () => ({
  PortalPage: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));
vi.mock("../../playback/components/AtlasTheaterPlayer", () => ({
  AtlasTheaterPlayer: (props: typeof mock.players[number]) => {
    mock.players.push(props);
    return <div data-testid="player">Player</div>;
  },
}));
vi.mock("./SportsCurrentlyLive", () => ({ SportsCurrentlyLive: () => null }));
vi.mock("./SportsLiveChannels", () => ({ SportsLiveChannels: () => null }));
vi.mock("../services/followedSportsRefresh", () => ({
  startFollowedSportsRefresh: () => () => undefined,
}));
vi.mock("../services/liveAvailabilityRefresh", () => ({
  startLiveAvailabilityRefresh: () => () => undefined,
}));
vi.mock("../services/playbackOptions", () => ({
  loadSportsPlaybackOptions: async () => [{ optionId: "primary", label: "Primary", configured: true }],
  preferredSportsPlaybackOption: () => "primary",
}));

function owned(id: string): SportsLiveSessionResult {
  return {
    atlasChannelId: "fixture-channel", liveSessionId: id, ttlSeconds: 2,
    releaseCapability: "credential-" + id, playbackOptionId: "primary",
    session: {
      available: true, action: "watch_now", label: "Watch Now", backend: "jellyfin",
      sourceType: "live", provider: "jellyfin", requestedTargetId: "fixture",
      playableTargetId: "fixture", title: "Fixture", mediaType: "tv", canSeek: false,
      playbackBootstrapUrl: "", playbackCapability: "fixture",
      audioTracks: [], subtitleTracks: [],
    },
  };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
let root: Root, container: HTMLDivElement;
beforeEach(async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers();
  mock.players.length = 0;
  mock.create.mockReset().mockResolvedValue(owned("first"));
  mock.heartbeat.mockReset().mockResolvedValue({ ttlSeconds: 2 });
  mock.release.mockReset().mockResolvedValue(undefined);
  container = document.createElement("div"); document.body.append(container);
  root = createRoot(container);
  await act(async () => root.render(<SportsPageClient />));
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove(); vi.useRealTimers();
});
async function click(label: string) {
  const button = [...container.querySelectorAll("button")].find((item) => item.textContent === label);
  expect(button).toBeDefined();
  await act(async () => button!.click());
}
async function failCurrent() {
  const player = mock.players.at(-1)!;
  expect(player).toBeDefined();
  await act(async () => player.onTerminalError(player.session));
  return player;
}

it.each(["resolve", "reject"] as const)("does not renew after a late heartbeat %s", async (outcome) => {
  const heartbeat = deferred<{ ttlSeconds: number }>();
  const release = deferred<void>();
  mock.heartbeat.mockReturnValueOnce(heartbeat.promise);
  mock.release.mockReturnValueOnce(release.promise);
  await click("Watch fixture");
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  expect(mock.heartbeat).toHaveBeenCalledExactlyOnceWith("first");
  const player = await failCurrent();
  expect(container.querySelector('[data-testid="player"]')).toBeNull();
  expect(mock.release).toHaveBeenCalledExactlyOnceWith("first", { releaseCapability: "credential-first" });
  await act(async () => {
    if (outcome === "resolve") heartbeat.resolve({ ttlSeconds: 2 });
    else heartbeat.reject(new Error("401 fixture"));
  });
  await act(async () => player.onTerminalError(player.session));
  await click("Close live playback");
  await click("Watch fixture");
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(mock.heartbeat).toHaveBeenCalledTimes(1);
  expect(mock.release).toHaveBeenCalledTimes(1);
  expect(mock.create).toHaveBeenCalledTimes(1);
  await act(async () => release.resolve());
  mock.create.mockResolvedValueOnce(owned("second"));
  await click("Watch fixture");
  expect(mock.create).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  expect(mock.heartbeat).toHaveBeenLastCalledWith("second");
});

it("retains failed cleanup, blocks replacement, and retries the exact credential on Close", async () => {
  mock.release.mockRejectedValueOnce(new Error("503 fixture"));
  await click("Watch fixture");
  await failCurrent();
  expect(container.textContent).toContain("cleanup could not be confirmed");
  await click("Watch fixture");
  await click("Primary");
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(mock.create).toHaveBeenCalledTimes(1);
  expect(mock.heartbeat).not.toHaveBeenCalled();
  expect(mock.release).toHaveBeenCalledTimes(1);
  await click("Close live playback");
  expect(mock.release).toHaveBeenNthCalledWith(2, "first", { releaseCapability: "credential-first" });
  expect(container.textContent).toContain("session was released");
  mock.create.mockResolvedValueOnce(owned("second"));
  await click("Watch fixture");
  expect(mock.create).toHaveBeenCalledTimes(2);
});

it("ignores an old player's fatal callback after a same-channel replacement", async () => {
  await click("Watch fixture");
  const old = mock.players.at(-1)!;
  mock.create.mockResolvedValueOnce(owned("second"));
  await click("Watch fixture");
  expect(mock.release).toHaveBeenCalledTimes(1);
  await act(async () => old.onTerminalError(old.session));
  expect(mock.release).toHaveBeenCalledTimes(1);
  expect(container.querySelector('[data-testid="player"]')).not.toBeNull();
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  expect(mock.heartbeat).toHaveBeenCalledExactlyOnceWith("second");
});

it("joins pending terminal cleanup when the page unmounts", async () => {
  const release = deferred<void>();
  mock.release.mockReturnValueOnce(release.promise);
  await click("Watch fixture");
  await failCurrent();
  await act(async () => root.render(null));
  expect(mock.release).toHaveBeenCalledTimes(1);
  await act(async () => release.resolve());
  expect(mock.release).toHaveBeenCalledTimes(1);
});
