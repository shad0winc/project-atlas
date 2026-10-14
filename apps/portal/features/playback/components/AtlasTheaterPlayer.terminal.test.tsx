// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AtlasTheaterPlayer } from "./AtlasTheaterPlayer";
import type { PlaybackSession } from "../types/session";

vi.mock("../services/stream", () => ({ bootstrapPlaybackStream: async () => ({
  streamUrl: "https://playback.example.test/fixture.m3u8",
}) }));
const mock = vi.hoisted(() => ({
  handlers: new Map<string, (event: string, data: Record<string, unknown>) => void>(),
  created: vi.fn(), destroyed: vi.fn(),
}));
vi.mock("hls.js", () => ({ default: class {
  static Events = { ERROR: "error", FRAG_LOADED: "loaded", FRAG_BUFFERED: "buffered" };
  static isSupported() { return true; }
  constructor() { mock.created(); }
  on(event: string, callback: (event: string, data: Record<string, unknown>) => void) {
    mock.handlers.set(event, callback);
  }
  attachMedia() {}
  loadSource() {}
  destroy() { mock.destroyed(); }
} }));
const session: PlaybackSession = {
  available: true, action: "watch_now", label: "Watch Now", backend: "jellyfin",
  sourceType: "live", provider: "jellyfin", requestedTargetId: "fixture",
  playableTargetId: "fixture", title: "Fixture", mediaType: "tv", canSeek: false,
  playbackBootstrapUrl: "", playbackCapability: "fixture",
  audioTracks: [], subtitleTracks: [],
};
let root: Root, container: HTMLDivElement;
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  mock.handlers.clear(); mock.created.mockClear(); mock.destroyed.mockClear();
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("");
  container = document.createElement("div"); document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks();
});
async function flush() {
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(mock.handlers.has("error")).toBe(true);
}
it("preserves recoverable HLS errors and reports a terminal error exactly once", async () => {
  const notify = vi.fn();
  await act(async () => root.render(<AtlasTheaterPlayer session={session} onTerminalError={notify} />));
  await flush();
  const error = mock.handlers.get("error")!;
  await act(async () => error("error", { fatal: false }));
  expect(notify).not.toHaveBeenCalled(); expect(mock.destroyed).not.toHaveBeenCalled();
  await act(async () => { error("error", { fatal: true }); error("error", { fatal: true }); });
  expect(notify).toHaveBeenCalledExactlyOnceWith(session);
  expect(mock.destroyed).toHaveBeenCalledTimes(1);
});
it("uses the latest callback without restarting playback and ignores events after unmount", async () => {
  const old = vi.fn(), current = vi.fn();
  await act(async () => root.render(<AtlasTheaterPlayer session={session} onTerminalError={old} />));
  await flush();
  const error = mock.handlers.get("error")!;
  await act(async () => root.render(<AtlasTheaterPlayer session={session} onTerminalError={current} />));
  expect(mock.created).toHaveBeenCalledTimes(1);
  await act(async () => error("error", { fatal: true }));
  expect(old).not.toHaveBeenCalled(); expect(current).toHaveBeenCalledExactlyOnceWith(session);
  await act(async () => root.render(null));
  await act(async () => error("error", { fatal: true }));
  expect(current).toHaveBeenCalledTimes(1);
});
