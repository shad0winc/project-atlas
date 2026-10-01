import { afterEach, describe, expect, it, vi } from "vitest";
import {
  loginBrowserSession,
  logoutBrowserSession,
  refreshBrowserIdentity,
  refreshBrowserSession,
  restoreBrowserSession
} from "./browser-auth";
import { registerAtlasAuthLifecycle } from "../auth/session-lifecycle";
import type { AtlasAuthSession } from "../auth/types";

const user = {
  user_id: "usr_one",
  username: "one",
  display_name: "One",
  first_name: null,
  last_name: null,
  email: null,
  discord_account: null,
  email_notifications_enabled: false,
  discord_notifications_enabled: false,
  roles: ["member"],
  provider: "jellyfin",
  granted_permission_patterns: [],
  denied_permission_patterns: []
};
const current: AtlasAuthSession = {
  tokens: { accessToken: "old", refreshToken: "", tokenType: "bearer" },
  user
};
function supportLocks() {
  let queue = Promise.resolve();
  vi.stubGlobal("navigator", {
    locks: {
      request: vi.fn((_name: string, callback: () => Promise<unknown>) => {
        const pending = queue.then(callback);
        queue = pending.then(
          () => {},
          () => {}
        );
        return pending;
      })
    }
  });
}
function tokenResponse() {
  return Response.json({ access_token: "fresh-access", token_type: "bearer" });
}
afterEach(() => vi.unstubAllGlobals());

describe("browser authentication", () => {
  it("uses cookie credentials and returns no JavaScript refresh credential", async () => {
    supportLocks();
    const fetch = vi.fn().mockResolvedValue(tokenResponse());
    vi.stubGlobal("fetch", fetch);
    const tokens = await loginBrowserSession({ username: "one", password: "example" });
    expect(tokens.refreshToken).toBe("");
    const [path, options] = fetch.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/v1/auth/browser/login");
    expect(options.credentials).toBe("same-origin");
    expect(new Headers(options.headers).get("X-Atlas-Browser-Session")).toBe("1");
    expect(options.cache).toBe("no-store");
  });
  it("restores the authoritative user and shares overlapping startup requests", async () => {
    supportLocks();
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(tokenResponse())
      .mockResolvedValueOnce(Response.json(user));
    vi.stubGlobal("fetch", fetch);
    const first = restoreBrowserSession();
    const second = restoreBrowserSession();
    expect(first).toBe(second);
    expect((await first).user.user_id).toBe("usr_one");
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/auth/browser/refresh");
    expect(fetch.mock.calls[1][0]).toBe("/api/v1/auth/me");
  });
  it("does not reuse a completed startup result", async () => {
    supportLocks();
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(tokenResponse())
      .mockResolvedValueOnce(Response.json(user))
      .mockResolvedValueOnce(new Response(null, { status: 401 }));
    vi.stubGlobal("fetch", fetch);
    await restoreBrowserSession();
    await expect(restoreBrowserSession()).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(3);
  });
  it("rejects a rotated session belonging to a different account", async () => {
    supportLocks();
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(tokenResponse())
      .mockResolvedValueOnce(Response.json({ ...user, user_id: "usr_two" }));
    vi.stubGlobal("fetch", fetch);
    await expect(refreshBrowserIdentity(current)).rejects.toThrow(/account changed/);
    expect(current.user.user_id).toBe("usr_one");
  });
  it("rejects identity validation without recursively refreshing", async () => {
    supportLocks();
    const recursiveRefresh = vi.fn();
    const unregister = registerAtlasAuthLifecycle({
      refreshAccessToken: recursiveRefresh,
      expireSession: vi.fn()
    });
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(tokenResponse())
      .mockResolvedValueOnce(new Response(null, { status: 401 }));
    vi.stubGlobal("fetch", fetch);
    try {
      await expect(refreshBrowserIdentity(current)).rejects.toThrow();
      expect(recursiveRefresh).not.toHaveBeenCalled();
      expect(fetch).toHaveBeenCalledTimes(2);
    } finally {
      unregister();
    }
  });
  it("refreshes the profile for the same authenticated user", async () => {
    supportLocks();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(tokenResponse())
        .mockResolvedValueOnce(Response.json({ ...user, display_name: "Updated" }))
    );
    expect((await refreshBrowserIdentity(current)).user.display_name).toBe("Updated");
  });
  it("serializes cookie rotation requests instead of replaying one cookie concurrently", async () => {
    supportLocks();
    let active = 0;
    let maximum = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        active += 1;
        maximum = Math.max(maximum, active);
        await new Promise((resolve) => setTimeout(resolve, 5));
        active -= 1;
        return tokenResponse();
      })
    );
    await Promise.all([refreshBrowserSession(), refreshBrowserSession()]);
    expect(maximum).toBe(1);
  });
  it("reports logout network failure without pretending revocation succeeded", async () => {
    supportLocks();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(logoutBrowserSession()).rejects.toThrow();
  });
  it("sends no refresh-token body on logout", async () => {
    supportLocks();
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await logoutBrowserSession();
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/auth/browser/logout");
    expect(fetch.mock.calls[0][1].body).toBeUndefined();
  });
  it("fails clearly if secure cross-tab coordination is unavailable", async () => {
    vi.stubGlobal("navigator", {});
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(refreshBrowserSession()).rejects.toThrow(/coordination/);
    expect(fetch).not.toHaveBeenCalled();
  });
});
