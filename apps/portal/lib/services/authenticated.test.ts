import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAtlasAuthSession, writeAtlasAuthSession } from "../auth/storage";
import type { AtlasAuthSession } from "../auth/types";

import {
  authenticatedAtlasApiRequest,
  authenticatedAtlasApiRequestWithMetadata
} from "./authenticated";

function createSession(accessToken: string): AtlasAuthSession {
  return {
    tokens: {
      accessToken,
      refreshToken: "refresh-token",
      tokenType: "bearer"
    },
    user: {}
  } as unknown as AtlasAuthSession;
}

afterEach(() => {
  clearAtlasAuthSession();
  vi.unstubAllGlobals();
});

describe("authenticated Atlas service requests", () => {
  it("uses the normalized access token from the active session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: {
          "Content-Type": "application/json"
        }
      })
    );

    vi.stubGlobal("fetch", fetchMock);
    writeAtlasAuthSession(createSession("  active-access-token  "));

    await expect(
      authenticatedAtlasApiRequest<{ status: string }>("/health", {
        method: "GET"
      })
    ).resolves.toEqual({
      status: "ok"
    });

    expect(fetchMock).toHaveBeenCalledOnce();

    const requestOptions = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = new Headers(requestOptions.headers);

    expect(headers.get("Authorization")).toBe("Bearer active-access-token");
  });

  it("preserves authenticated response metadata and headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": "response-request-id",
          "X-Atlas-Live-Session-ID": "live-session-001",
          "X-Atlas-Live-Session-TTL": "90"
        }
      })
    );

    vi.stubGlobal("fetch", fetchMock);
    writeAtlasAuthSession(
      createSession("  active-access-token  ")
    );

    const response =
      await authenticatedAtlasApiRequestWithMetadata<{
        status: string;
      }>("/sports/live/channel-001/session", {
        method: "GET",
        cache: "no-store"
      });

    expect(response.data).toEqual({
      status: "ok"
    });

    expect(response.status).toBe(200);
    expect(response.requestId).toBe("response-request-id");

    expect(
      response.headers.get("X-Atlas-Live-Session-ID")
    ).toBe("live-session-001");

    expect(
      response.headers.get("X-Atlas-Live-Session-TTL")
    ).toBe("90");

    expect(fetchMock).toHaveBeenCalledOnce();

    const requestOptions =
      fetchMock.mock.calls[0]?.[1] as RequestInit;

    const requestHeaders =
      new Headers(requestOptions.headers);

    expect(
      requestHeaders.get("Authorization")
    ).toBe("Bearer active-access-token");
  });

  it("rejects a protected request when no session exists", async () => {
    await expect(authenticatedAtlasApiRequest("/dashboard/summary")).rejects.toThrow(
      "Atlas authentication session is unavailable."
    );
  });

  it("rejects a protected request when the session token is empty", async () => {
    writeAtlasAuthSession(createSession("   "));

    await expect(authenticatedAtlasApiRequest("/dashboard/summary")).rejects.toThrow(
      "Atlas authentication session is unavailable."
    );
  });
});
