import { afterEach, describe, expect, it, vi } from "vitest";

import { atlasApiRequest } from "./client";
import { AtlasApiError, AtlasApiNetworkError } from "./errors";
import { createAtlasApiRetryPolicy } from "./policy";

function successfulJsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function failedJsonResponse(status: number, detail = "Request failed."): Response {
  return new Response(
    JSON.stringify({
      detail
    }),
    {
      status,
      headers: {
        "Content-Type": "application/json"
      }
    }
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Atlas API retry orchestration", () => {
  it("preserves one-attempt behavior under the default policy", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(async () => failedJsonResponse(503, "Service unavailable."));

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      atlasApiRequest("/health", {
        requestId: "default-policy-request"
      })
    ).rejects.toMatchObject({
      name: "AtlasApiError",
      status: 503,
      kind: "unavailable"
    } satisfies Partial<AtlasApiError>);

    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("retries a retryable HTTP failure and returns the later success", async () => {
    vi.useFakeTimers();

    const fetchMock = vi
      .fn()
      .mockImplementationOnce(async () => failedJsonResponse(503, "Temporarily unavailable."))
      .mockImplementationOnce(async () =>
        successfulJsonResponse({
          status: "ok"
        })
      );

    vi.stubGlobal("fetch", fetchMock);

    const request = atlasApiRequest<{ status: string }>("/health", {
      requestId: "retry-success-request",
      retryPolicy: createAtlasApiRetryPolicy({
        maxRetries: 1,
        baseDelayMs: 25,
        maxDelayMs: 25
      })
    });

    const assertion = expect(request).resolves.toEqual({
      status: "ok"
    });

    await vi.advanceTimersByTimeAsync(25);
    await assertion;

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("retries a network failure and returns the later success", async () => {
    vi.useFakeTimers();

    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Connection refused"))
      .mockImplementationOnce(async () =>
        successfulJsonResponse({
          status: "recovered"
        })
      );

    vi.stubGlobal("fetch", fetchMock);

    const request = atlasApiRequest<{ status: string }>("/health", {
      requestId: "network-retry-request",
      retryPolicy: createAtlasApiRetryPolicy({
        maxRetries: 1,
        baseDelayMs: 10,
        maxDelayMs: 10
      })
    });

    const assertion = expect(request).resolves.toEqual({
      status: "recovered"
    });

    await vi.advanceTimersByTimeAsync(10);
    await assertion;

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("throws the final retryable error when the retry budget is exhausted", async () => {
    vi.useFakeTimers();

    const fetchMock = vi
      .fn()
      .mockImplementation(async () => failedJsonResponse(503, "Still unavailable."));

    vi.stubGlobal("fetch", fetchMock);

    const request = atlasApiRequest("/health", {
      requestId: "retry-exhausted-request",
      retryPolicy: createAtlasApiRetryPolicy({
        maxRetries: 2,
        baseDelayMs: 10,
        maxDelayMs: 20
      })
    });

    const assertion = expect(request).rejects.toMatchObject({
      name: "AtlasApiError",
      status: 503,
      detail: "Still unavailable.",
      kind: "unavailable"
    } satisfies Partial<AtlasApiError>);

    await vi.advanceTimersByTimeAsync(30);
    await assertion;

    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not retry a non-retryable HTTP failure", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(async () => failedJsonResponse(401, "Authentication required."));

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      atlasApiRequest("/protected", {
        requestId: "authentication-request",
        retryPolicy: createAtlasApiRetryPolicy({
          maxRetries: 3,
          baseDelayMs: 0,
          maxDelayMs: 0
        })
      })
    ).rejects.toMatchObject({
      name: "AtlasApiError",
      status: 401,
      kind: "authentication"
    } satisfies Partial<AtlasApiError>);

    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("uses bounded exponential delays between attempts", async () => {
    vi.useFakeTimers();

    const fetchMock = vi
      .fn()
      .mockImplementationOnce(async () => failedJsonResponse(503))
      .mockImplementationOnce(async () => failedJsonResponse(503))
      .mockImplementationOnce(async () => failedJsonResponse(503))
      .mockImplementationOnce(async () =>
        successfulJsonResponse({
          status: "ok"
        })
      );

    vi.stubGlobal("fetch", fetchMock);

    const request = atlasApiRequest<{ status: string }>("/health", {
      requestId: "backoff-request",
      retryPolicy: createAtlasApiRetryPolicy({
        maxRetries: 3,
        baseDelayMs: 100,
        maxDelayMs: 150
      })
    });

    const assertion = expect(request).resolves.toEqual({
      status: "ok"
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(99);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(149);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);

    await vi.advanceTimersByTimeAsync(150);
    await assertion;

    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("keeps the final network error type when retries are exhausted", async () => {
    vi.useFakeTimers();

    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("First failure"))
      .mockRejectedValueOnce(new TypeError("Second failure"));

    vi.stubGlobal("fetch", fetchMock);

    const request = atlasApiRequest("/health", {
      requestId: "network-exhausted-request",
      retryPolicy: createAtlasApiRetryPolicy({
        maxRetries: 1,
        baseDelayMs: 10,
        maxDelayMs: 10
      })
    });

    const assertion = expect(request).rejects.toBeInstanceOf(AtlasApiNetworkError);

    await vi.advanceTimersByTimeAsync(10);
    await assertion;

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
