import { afterEach, describe, expect, it, vi } from "vitest";

import {
  registerAtlasAuthLifecycle,
  resetAtlasAuthLifecycleForTests
} from "../auth/session-lifecycle";

import { atlasApiRequest } from "./client";
import {
  AtlasApiAuthenticationError,
  AtlasApiAuthorizationError,
  AtlasAuthenticationExpiredError
} from "./errors";

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  resetAtlasAuthLifecycleForTests();
});

describe("Atlas authenticated request orchestration", () => {
  it("refreshes once and replays a rejected authenticated request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(401, {
          detail: "Access token expired."
        })
      )
      .mockResolvedValueOnce(
        jsonResponse(200, {
          status: "ok"
        })
      );

    vi.stubGlobal("fetch", fetchMock);

    const refreshAccessToken = vi.fn().mockResolvedValue("replacement-access-token");

    registerAtlasAuthLifecycle({
      refreshAccessToken,
      expireSession: vi.fn()
    });

    await expect(
      atlasApiRequest<{ status: string }>("/protected", {
        accessToken: "original-access-token",
        requestId: "authenticated-replay"
      })
    ).resolves.toEqual({
      status: "ok"
    });

    expect(refreshAccessToken).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(2);

    const firstHeaders = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    const secondHeaders = new Headers(fetchMock.mock.calls[1]?.[1]?.headers);

    expect(firstHeaders.get("Authorization")).toBe("Bearer original-access-token");
    expect(secondHeaders.get("Authorization")).toBe("Bearer replacement-access-token");
  });

  it("does not refresh a forbidden request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(403, {
        detail: "Permission denied."
      })
    );

    vi.stubGlobal("fetch", fetchMock);

    const refreshAccessToken = vi.fn();

    registerAtlasAuthLifecycle({
      refreshAccessToken,
      expireSession: vi.fn()
    });

    await expect(
      atlasApiRequest("/protected", {
        accessToken: "valid-access-token"
      })
    ).rejects.toBeInstanceOf(AtlasApiAuthorizationError);

    expect(refreshAccessToken).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("returns the typed authentication error when refresh is disabled", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(401, {
          detail: "Authentication required."
        })
      )
    );

    registerAtlasAuthLifecycle({
      refreshAccessToken: vi.fn(),
      expireSession: vi.fn()
    });

    await expect(
      atlasApiRequest("/protected", {
        accessToken: "expired-token",
        retryAuthentication: false
      })
    ).rejects.toBeInstanceOf(AtlasApiAuthenticationError);
  });

  it("expires the session when refresh fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(401, {
          detail: "Access token expired."
        })
      )
    );

    const expireSession = vi.fn();

    registerAtlasAuthLifecycle({
      refreshAccessToken: vi.fn().mockRejectedValue(new Error("Refresh token expired.")),
      expireSession
    });

    await expect(
      atlasApiRequest("/protected", {
        accessToken: "expired-access-token"
      })
    ).rejects.toBeInstanceOf(AtlasAuthenticationExpiredError);

    expect(expireSession).toHaveBeenCalledOnce();
  });

  it("expires the session when the replay is also unauthorized", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(401, {
          detail: "Access token expired."
        })
      )
      .mockResolvedValueOnce(
        jsonResponse(401, {
          detail: "Replacement token rejected."
        })
      );

    vi.stubGlobal("fetch", fetchMock);

    const expireSession = vi.fn();

    registerAtlasAuthLifecycle({
      refreshAccessToken: vi.fn().mockResolvedValue("replacement-token"),
      expireSession
    });

    await expect(
      atlasApiRequest("/protected", {
        accessToken: "expired-token"
      })
    ).rejects.toBeInstanceOf(AtlasAuthenticationExpiredError);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(expireSession).toHaveBeenCalledOnce();
  });
});
