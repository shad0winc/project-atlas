import { afterEach, describe, expect, it, vi } from "vitest";

import { logoutAtlasSession } from "./auth";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Atlas authentication services", () => {
  it("revokes the normalized refresh token on logout", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 204
      })
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(logoutAtlasSession("  refresh-token  ")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledOnce();

    const [path, options] = fetchMock.mock.calls[0] as [string, RequestInit];

    expect(path).toBe("/api/v1/auth/logout");
    expect(options.method).toBe("POST");
    expect(options.cache).toBe("no-store");
    expect(options.body).toBe(
      JSON.stringify({
        refresh_token: "refresh-token"
      })
    );
  });

  it("rejects an empty refresh token without making a request", async () => {
    const fetchMock = vi.fn();

    vi.stubGlobal("fetch", fetchMock);

    await expect(logoutAtlasSession("   ")).rejects.toThrow("Atlas refresh token cannot be empty.");

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
