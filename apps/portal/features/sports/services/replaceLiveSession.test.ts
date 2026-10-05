import { beforeEach, describe, expect, it, vi } from "vitest";
import { createSportsLiveSession, releaseSportsLiveSession, type SportsLiveSessionResult } from "./sports";
import { replaceSportsLiveSession } from "./replaceLiveSession";
vi.mock("./sports", () => ({ createSportsLiveSession: vi.fn(), releaseSportsLiveSession: vi.fn() }));
const current = { liveSessionId: "owned-old", atlasChannelId: "sports-live-game" } as SportsLiveSessionResult;
beforeEach(() => vi.resetAllMocks());
describe("replacement at a one-session limit", () => {
  it("closes the existing owned stream before opening the selected alternative", async () => {
    const order: string[] = [];
    let active = 1;
    vi.mocked(releaseSportsLiveSession).mockImplementation(async id => { expect(id).toBe("owned-old"); order.push("release"); active--; });
    vi.mocked(createSportsLiveSession).mockImplementation(async () => {
      expect(active).toBe(0); active++; order.push("open"); return { liveSessionId: "owned-new" } as SportsLiveSessionResult;
    });
    await replaceSportsLiveSession({ current, channelId: current.atlasChannelId, optionId: "backup-1", detach: () => order.push("detach") });
    expect(order).toEqual(["detach", "release", "open"]);
    expect(active).toBe(1);
    expect(createSportsLiveSession).toHaveBeenCalledWith("sports-live-game", { signal: undefined }, "auto", "backup-1");
  });
  it("does not open another stream when cleanup fails or its outcome is uncertain", async () => {
    vi.mocked(releaseSportsLiveSession).mockRejectedValue(new Error("cleanup failed"));
    await expect(replaceSportsLiveSession({ current, channelId: current.atlasChannelId, optionId: "backup-1", detach: vi.fn() })).rejects.toThrow();
    expect(createSportsLiveSession).not.toHaveBeenCalled();
  });
  it("finishes cleanup even when the new request is cancelled", async () => {
    const controller = new AbortController(); controller.abort();
    await expect(replaceSportsLiveSession({ current, channelId: current.atlasChannelId, signal: controller.signal, detach: vi.fn() })).rejects.toThrow();
    expect(releaseSportsLiveSession).toHaveBeenCalledWith("owned-old");
    expect(createSportsLiveSession).not.toHaveBeenCalled();
  });
});
