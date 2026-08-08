import { afterEach, describe, expect, it, vi } from "vitest";

import {
  refreshAtlasAuthAccessToken,
  registerAtlasAuthLifecycle,
  resetAtlasAuthLifecycleForTests,
  subscribeAtlasAuthLifecycle
} from "./session-lifecycle";

afterEach(() => {
  resetAtlasAuthLifecycleForTests();
});

describe("Atlas authentication lifecycle", () => {
  it("shares one refresh operation across concurrent requests", async () => {
    let resolveRefresh: ((token: string) => void) | undefined;

    const refreshAccessToken = vi.fn(
      () =>
        new Promise<string>((resolve) => {
          resolveRefresh = resolve;
        })
    );

    registerAtlasAuthLifecycle({
      refreshAccessToken,
      expireSession: vi.fn()
    });

    const first = refreshAtlasAuthAccessToken();
    const second = refreshAtlasAuthAccessToken();

    expect(refreshAccessToken).toHaveBeenCalledOnce();

    resolveRefresh?.("replacement-access-token");

    await expect(first).resolves.toBe("replacement-access-token");
    await expect(second).resolves.toBe("replacement-access-token");
  });

  it("expires the session when token rotation fails", async () => {
    const failure = new Error("Refresh rejected.");
    const expireSession = vi.fn();

    registerAtlasAuthLifecycle({
      refreshAccessToken: vi.fn().mockRejectedValue(failure),
      expireSession
    });

    await expect(refreshAtlasAuthAccessToken()).rejects.toBe(failure);

    expect(expireSession).toHaveBeenCalledOnce();
  });

  it("publishes refresh and expiration observations", async () => {
    const onRefreshStarted = vi.fn();
    const onRefreshSucceeded = vi.fn();
    const onSessionExpired = vi.fn();

    subscribeAtlasAuthLifecycle({
      onRefreshStarted,
      onRefreshSucceeded,
      onSessionExpired
    });

    registerAtlasAuthLifecycle({
      refreshAccessToken: vi.fn().mockResolvedValue("replacement-token"),
      expireSession: vi.fn()
    });

    await refreshAtlasAuthAccessToken();

    expect(onRefreshStarted).toHaveBeenCalledOnce();
    expect(onRefreshSucceeded).toHaveBeenCalledOnce();
    expect(onSessionExpired).not.toHaveBeenCalled();
  });

  it("isolates observer failures from refresh behavior", async () => {
    subscribeAtlasAuthLifecycle({
      onRefreshStarted: () => {
        throw new Error("Observer failed.");
      },
      onRefreshSucceeded: () => {
        throw new Error("Observer failed.");
      }
    });

    registerAtlasAuthLifecycle({
      refreshAccessToken: vi.fn().mockResolvedValue("valid-token"),
      expireSession: vi.fn()
    });

    await expect(refreshAtlasAuthAccessToken()).resolves.toBe("valid-token");
  });
});
