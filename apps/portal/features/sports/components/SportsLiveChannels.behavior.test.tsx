// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SportsLiveChannels } from "./SportsLiveChannels";
import { loadSportsLiveChannels } from "../services/liveChannels";
import {
  loadSportsFollows,
  followSports,
  unfollowSports,
} from "../services/sports";
vi.mock("../services/sports", () => ({
  loadSportsFollows: vi.fn(),
  followSports: vi.fn(),
  unfollowSports: vi.fn(),
}));
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
  vi.mocked(loadSportsFollows).mockResolvedValue([]);
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
  it("uses Events search and the page's channel follows without a duplicate save-state read", async () => {
    const changed = vi.fn(async () => {});
    const channelFollow = {
      subscriptionId: "channel-save",
      type: "channel" as const,
      provider: "atlas",
      providerId: ready.atlasChannelId,
      name: ready.name,
      userId: "owner",
      enabled: true,
      record: false,
      createdAt: null,
    };
    await act(async () =>
      root.render(
        <SportsLiveChannels
          onWatchLive={vi.fn(async () => {})}
          searchQuery="Red Zone"
          managedFollows={[channelFollow]}
          onFollowsChanged={changed}
        />,
      ),
    );
    await flush();
    expect(container.textContent).toContain("NFL RedZone");
    expect(container.textContent).toContain("Schedule unavailable");
    expect(container.querySelector("input")).toBeNull();
    expect(loadSportsFollows).not.toHaveBeenCalled();
    const unfollow = container.querySelector(
      '[aria-label="Unfollow NFL RedZone"]',
    ) as HTMLButtonElement;
    await act(async () => unfollow.click());
    await flush();
    expect(unfollowSports).toHaveBeenCalledWith("channel-save");
    expect(changed).toHaveBeenCalledOnce();
    await act(async () =>
      root.render(
        <SportsLiveChannels
          onWatchLive={vi.fn(async () => {})}
          searchQuery="Monday Night Football"
          managedFollows={[]}
          onFollowsChanged={changed}
        />,
      ),
    );
    expect(container.textContent).toContain(
      "No live channels match your search.",
    );
  });

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

const persisted = {
  subscriptionId: "sub-redzone",
  type: "channel" as const,
  provider: "atlas",
  providerId: ready.atlasChannelId,
  name: ready.name,
  userId: "user-one",
  enabled: true,
  record: false,
  createdAt: null,
};
function button(label: string) {
  return Array.from(container.querySelectorAll("button")).find(
    (item) => item.textContent === label,
  )!;
}
async function search(query: string) {
  await act(async () => {
    const input = container.querySelector('input[type="search"]')!;
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )!.set!.call(input, query);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("durable channel follows", () => {
  it("saves the stable channel identity without starting playback and removes it after unfollow", async () => {
    vi.mocked(followSports).mockResolvedValue(persisted);
    const watch = await mount();
    await act(async () => button("Follow").click());
    expect(followSports).toHaveBeenCalledWith("channel", ready.atlasChannelId);
    expect(button("Unfollow")).toBeDefined();
    expect(watch).not.toHaveBeenCalled();
    await act(async () => button("Unfollow").click());
    expect(unfollowSports).toHaveBeenCalledWith("sub-redzone");
    expect(button("Follow")).toBeDefined();
  });
  it("loads persisted follows and supports followed-only filtering", async () => {
    vi.mocked(loadSportsFollows).mockResolvedValue([persisted]);
    vi.mocked(loadSportsLiveChannels).mockResolvedValue([
      ready,
      { ...ready, name: "NBA TV", atlasChannelId: "sports-live-nba-tv" },
    ]);
    await mount();
    expect(container.textContent).toContain("NBA TV");
    expect(button("Unfollow")).toBeDefined();
    await act(async () =>
      (
        container.querySelector('input[type="checkbox"]') as HTMLInputElement
      ).click(),
    );
    expect(container.textContent).toContain("NFL RedZone");
    expect(container.textContent).not.toContain("NBA TV");
    expect(followSports).not.toHaveBeenCalled();
  });
  it("keeps disappeared saved channels removable without offering playback", async () => {
    vi.mocked(loadSportsLiveChannels).mockResolvedValue([]);
    vi.mocked(loadSportsFollows).mockResolvedValue([persisted]);
    await mount();
    expect(container.textContent).toContain("Channel currently unavailable");
    expect(button("Watch Live")).toBeUndefined();
    await act(async () => button("Unfollow").click());
    expect(unfollowSports).toHaveBeenCalledWith("sub-redzone");
    expect(container.textContent).not.toContain("NFL RedZone");
  });
  it("preserves saved state when unfollow fails", async () => {
    vi.mocked(loadSportsFollows).mockResolvedValue([persisted]);
    vi.mocked(unfollowSports).mockRejectedValue(new Error("offline"));
    await mount();
    await act(async () => button("Unfollow").click());
    expect(button("Unfollow")).toBeDefined();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "Refresh to check",
    );
  });
  it("does not allow duplicate in-flight follow changes", async () => {
    let resolve!: (value: typeof persisted) => void;
    vi.mocked(followSports).mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    await mount();
    await act(async () => {
      button("Follow").click();
    });
    expect(button("Saving...").disabled).toBe(true);
    expect(followSports).toHaveBeenCalledTimes(1);
    await act(async () => resolve(persisted));
    expect(button("Unfollow")).toBeDefined();
  });
  it("shows a follow-read failure instead of pretending no saved channels exist", async () => {
    vi.mocked(loadSportsFollows).mockRejectedValue(new Error("offline"));
    await mount();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(button("Follow")).toBeUndefined();
    expect(followSports).not.toHaveBeenCalled();
  });
  it.each([
    ["Red Zone", "NFL RedZone"],
    ["nba", "NBA TV"],
    ["MLB", "MLB Network"],
    ["nhl", "NHL Network"],
    ["soccer", "Soccer Live"],
    ["thursday night", "Thursday Night Football"],
    ["monday night", "Monday Night Football"],
  ])(
    "searches all registered league channels for %s",
    async (query, expected) => {
      const names = [
        "NFL RedZone",
        "NBA TV",
        "MLB Network",
        "NHL Network",
        "Soccer Live",
        "Thursday Night Football",
        "Monday Night Football",
      ];
      vi.mocked(loadSportsLiveChannels).mockResolvedValue(
        names.map((name, index) => ({
          atlasChannelId: `sports-live-fixture-${index}`,
          name,
          playbackConfigured: true,
        })),
      );
      const watch = await mount();
      await search(query);
      expect(container.querySelectorAll("li")).toHaveLength(1);
      expect(container.querySelector("li")?.textContent).toContain(expected);
      expect(watch).not.toHaveBeenCalled();
    },
  );
});
