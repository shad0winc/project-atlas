import { afterEach, describe, expect, it, vi } from "vitest";

import { atlasApiRequest } from "./client";
import {
  AtlasApiAbortError,
  AtlasApiError,
  AtlasApiNetworkError,
  AtlasApiResponseError,
  AtlasApiTimeoutError
} from "./errors";

function successfulJsonResponse(
  payload: unknown,
  {
    status = 200,
    requestId
  }: Readonly<{
    status?: number;
    requestId?: string;
  }> = {}
): Response {
  const headers = new Headers({
    "Content-Type": "application/json"
  });

  if (requestId) {
    headers.set("X-Request-ID", requestId);
  }

  return new Response(JSON.stringify(payload), {
    status,
    headers
  });
}

function rejectedOnAbortFetch(): typeof fetch {
  return vi.fn(
    (_input: RequestInfo | URL, init?: RequestInit): Promise<Response> =>
      new Promise((_resolve, reject) => {
        const signal = init?.signal;

        const rejectAbort = (): void => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        };

        if (signal?.aborted) {
          rejectAbort();
          return;
        }

        signal?.addEventListener("abort", rejectAbort, {
          once: true
        });
      })
  ) as typeof fetch;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("atlasApiRequest", () => {
  it("builds the versioned request with JSON and authentication headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      successfulJsonResponse({
        status: "ok"
      })
    );

    vi.stubGlobal("fetch", fetchMock);

    const payload = await atlasApiRequest<{ status: string }>("/example", {
      method: "POST",
      body: {
        value: "atlas"
      },
      accessToken: "  access-token  ",
      requestId: "request-123",
      cache: "no-store"
    });

    expect(payload).toEqual({
      status: "ok"
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [path, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(request.headers);

    expect(path).toBe("/api/v1/example");
    expect(request.method).toBe("POST");
    expect(request.cache).toBe("no-store");
    expect(request.body).toBe(JSON.stringify({ value: "atlas" }));
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(headers.get("X-Request-ID")).toBe("request-123");
  });

  it("preserves a request ID supplied through headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      successfulJsonResponse({
        status: "ok"
      })
    );

    vi.stubGlobal("fetch", fetchMock);

    await atlasApiRequest("/health", {
      headers: {
        "X-Request-ID": "header-request-id"
      }
    });

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(request.headers);

    expect(headers.get("X-Request-ID")).toBe("header-request-id");
  });

  it("generates a request ID when the caller does not provide one", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      successfulJsonResponse({
        status: "ok"
      })
    );

    vi.stubGlobal("fetch", fetchMock);

    await atlasApiRequest("/health");

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(request.headers);
    const requestId = headers.get("X-Request-ID");

    expect(requestId).toBeTruthy();
    expect(requestId?.trim()).not.toBe("");
  });

  it("returns undefined for a 204 response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(null, {
          status: 204
        })
      )
    );

    await expect(atlasApiRequest<void>("/empty")).resolves.toBeUndefined();
  });

  it("raises a response error when a successful response is not valid JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("not-json", {
          status: 200,
          headers: {
            "Content-Type": "text/plain",
            "X-Request-ID": "response-error-request"
          }
        })
      )
    );

    await expect(
      atlasApiRequest("/invalid-response", {
        requestId: "client-request"
      })
    ).rejects.toMatchObject({
      name: "AtlasApiResponseError",
      status: 200,
      contentType: "text/plain",
      requestId: "response-error-request",
      method: "GET",
      path: "/api/v1/invalid-response"
    } satisfies Partial<AtlasApiResponseError>);
  });

  it.each([
    [401, "authentication"],
    [403, "authorization"],
    [400, "validation"],
    [422, "validation"],
    [409, "conflict"],
    [429, "rate-limit"],
    [502, "unavailable"],
    [503, "unavailable"],
    [504, "unavailable"],
    [500, "http"]
  ] as const)("classifies HTTP status %i as %s", async (status, kind) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        successfulJsonResponse(
          {
            detail: "Request failed."
          },
          {
            status,
            requestId: `response-${status}`
          }
        )
      )
    );

    await expect(
      atlasApiRequest("/failure", {
        requestId: "client-request"
      })
    ).rejects.toMatchObject({
      name: "AtlasApiError",
      status,
      detail: "Request failed.",
      kind,
      requestId: `response-${status}`,
      method: "GET",
      path: "/api/v1/failure"
    } satisfies Partial<AtlasApiError>);
  });

  it("falls back to a status message for a non-JSON HTTP failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("upstream failure", {
          status: 502,
          headers: {
            "Content-Type": "text/plain"
          }
        })
      )
    );

    await expect(
      atlasApiRequest("/failure", {
        requestId: "fallback-request"
      })
    ).rejects.toMatchObject({
      name: "AtlasApiError",
      status: 502,
      detail: "Atlas API request failed with status 502.",
      kind: "unavailable",
      requestId: "fallback-request"
    } satisfies Partial<AtlasApiError>);
  });

  it("raises a network error when fetch fails independently of cancellation", async () => {
    const failure = new TypeError("Connection refused");

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(failure));

    await expect(
      atlasApiRequest("/health", {
        requestId: "network-request"
      })
    ).rejects.toMatchObject({
      name: "AtlasApiNetworkError",
      requestId: "network-request",
      method: "GET",
      path: "/api/v1/health",
      cause: failure
    } satisfies Partial<AtlasApiNetworkError>);
  });

  it("raises a timeout error when the request exceeds its timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", rejectedOnAbortFetch());

    const request = atlasApiRequest("/slow", {
      requestId: "timeout-request",
      timeoutMs: 25
    });

    const assertion = expect(request).rejects.toMatchObject({
      name: "AtlasApiTimeoutError",
      requestId: "timeout-request",
      method: "GET",
      path: "/api/v1/slow",
      timeoutMs: 25
    } satisfies Partial<AtlasApiTimeoutError>);

    await vi.advanceTimersByTimeAsync(25);
    await assertion;
  });

  it("raises an abort error when the caller cancels the request", async () => {
    vi.stubGlobal("fetch", rejectedOnAbortFetch());

    const controller = new AbortController();

    const request = atlasApiRequest("/cancelled", {
      requestId: "abort-request",
      signal: controller.signal,
      timeoutMs: 10_000
    });

    controller.abort("caller cancelled");

    await expect(request).rejects.toMatchObject({
      name: "AtlasApiAbortError",
      requestId: "abort-request",
      method: "GET",
      path: "/api/v1/cancelled"
    } satisfies Partial<AtlasApiAbortError>);
  });

  it("rejects an empty access token before calling fetch", async () => {
    const fetchMock = vi.fn();

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      atlasApiRequest("/protected", {
        accessToken: "   "
      })
    ).rejects.toThrow("Atlas access token cannot be empty.");

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects invalid timeout values before calling fetch", async () => {
    const fetchMock = vi.fn();

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      atlasApiRequest("/health", {
        timeoutMs: 0
      })
    ).rejects.toThrow("Atlas API timeout must be a positive integer.");

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
