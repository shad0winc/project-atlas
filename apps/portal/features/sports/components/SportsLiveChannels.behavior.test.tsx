// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SportsLiveChannels } from "./SportsLiveChannels";
import { loadSportsLiveChannels } from "../services/liveChannels";
vi.mock("../services/liveChannels", () => ({
  loadSportsLiveChannels: vi.fn(),
}));
let root: Root;
let container: HTMLDivElement;
const ready = {
  atlasChannelId: "sports-live-nfl-redzone",
  name: "NFL RedZone",
  playbackConfigured: true,
};
async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.mocked(loadSportsLiveChannels).mockResolvedValue([ready]);
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.resetAllMocks();
});
async function mount(watch = vi.fn(async () => {})) {
  await act(async () =>
    root.render(<SportsLiveChannels onWatchLive={watch} />),
  );
  await flush();
  return watch;
}
describe("standalone live channel discovery", () => {
  it("finds RedZone including the spaced search spelling without opening playback", async () => {
    const watch = await mount();
    await act(async () => {
      const input = container.querySelector("input")!;
      const setter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )!.set!;
      setter.call(input, "unmatched-channel");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(container.textContent).toContain(
      "No live channels match your search.",
    );
    await act(async () => {
      const input = container.querySelector("input")!;
      const setter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )!.set!;
      setter.call(input, "Red Zone");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(container.textContent).toContain("NFL RedZone");
    expect(watch).not.toHaveBeenCalled();
    const button = Array.from(container.querySelectorAll("button")).find(
      (item) => item.textContent === "Watch Live",
    )!;
    await act(async () => button.click());
    expect(watch).toHaveBeenCalledWith(ready.atlasChannelId);
  });
  it("shows setup pending instead of Watch Live when identity binding is missing", async () => {
    vi.mocked(loadSportsLiveChannels).mockResolvedValue([
      { ...ready, playbackConfigured: false },
    ]);
    await mount();
    expect(container.textContent).toContain("Playback setup pending");
    expect(container.textContent).not.toContain("Watch Live");
  });
  it("distinguishes failure from empty results and supports explicit retry", async () => {
    vi.mocked(loadSportsLiveChannels).mockRejectedValueOnce(
      new Error("unavailable"),
    );
    await mount();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(container.textContent).not.toContain(
      "No live channels are configured",
    );
    await act(async () => container.querySelector("button")!.click());
    await flush();
    expect(container.textContent).toContain("NFL RedZone");
  });
  it("blocks additional Watch Live clicks while opening a stream", async () => {
    let resolve!: () => void;
    const watch = vi.fn(
      () =>
        new Promise<void>((done) => {
          resolve = done;
        }),
    );
    await mount(watch);
    const button = Array.from(container.querySelectorAll("button")).find(
      (item) => item.textContent === "Watch Live",
    )!;
    await act(async () => button.click());
    expect(button.disabled).toBe(true);
    await act(async () => button.click());
    expect(watch).toHaveBeenCalledTimes(1);
    await act(async () => resolve());
  });
});
