import { describe, expect, it } from "vitest";

import { AtlasApiError, AtlasApiNetworkError } from "./errors";
import {
  ATLAS_API_DEFAULT_RETRY_POLICY,
  atlasApiRetryDelayMs,
  createAtlasApiRetryPolicy,
  isRetryableAtlasApiError,
  shouldRetryAtlasApiRequest
} from "./policy";

function httpError(
  status: number,
  kind:
    | "authentication"
    | "authorization"
    | "validation"
    | "conflict"
    | "rate-limit"
    | "unavailable"
    | "http"
): AtlasApiError {
  return new AtlasApiError({
    status,
    detail: "Request failed.",
    method: "GET",
    path: "/api/v1/example",
    requestId: "request-123",
    kind
  });
}

describe("Atlas API retry policy", () => {
  it("defaults to zero retries so existing client behavior remains unchanged", () => {
    expect(ATLAS_API_DEFAULT_RETRY_POLICY).toEqual({
      maxRetries: 0,
      baseDelayMs: 250,
      maxDelayMs: 5_000
    });

    expect(
      shouldRetryAtlasApiRequest({
        error: httpError(503, "unavailable"),
        retryCount: 0
      })
    ).toBe(false);
  });

  it("creates an immutable normalized policy", () => {
    const policy = createAtlasApiRetryPolicy({
      maxRetries: 3,
      baseDelayMs: 100,
      maxDelayMs: 1_000
    });

    expect(policy).toEqual({
      maxRetries: 3,
      baseDelayMs: 100,
      maxDelayMs: 1_000
    });
    expect(Object.isFrozen(policy)).toBe(true);
  });

  it.each([
    ["maximum retries", { maxRetries: -1 }],
    ["retry base delay", { baseDelayMs: 1.5 }],
    ["retry maximum delay", { maxDelayMs: Number.NaN }]
  ])("rejects an invalid %s", (_name, options) => {
    expect(() => createAtlasApiRetryPolicy(options)).toThrow("must be a non-negative integer");
  });

  it("rejects a maximum delay below the base delay", () => {
    expect(() =>
      createAtlasApiRetryPolicy({
        baseDelayMs: 500,
        maxDelayMs: 250
      })
    ).toThrow("maximum delay cannot be less than the base delay");
  });

  it("classifies network failures as retryable", () => {
    const error = new AtlasApiNetworkError({
      method: "GET",
      path: "/api/v1/health",
      requestId: "network-request",
      cause: new TypeError("Connection refused")
    });

    expect(isRetryableAtlasApiError(error)).toBe(true);
  });

  it.each([
    [429, "rate-limit"],
    [502, "unavailable"],
    [503, "unavailable"],
    [504, "unavailable"]
  ] as const)("classifies HTTP status %i as retryable", (status, kind) => {
    expect(isRetryableAtlasApiError(httpError(status, kind))).toBe(true);
  });

  it.each([
    [400, "validation"],
    [401, "authentication"],
    [403, "authorization"],
    [409, "conflict"],
    [422, "validation"],
    [500, "http"]
  ] as const)("classifies HTTP status %i as non-retryable", (status, kind) => {
    expect(isRetryableAtlasApiError(httpError(status, kind))).toBe(false);
  });

  it("permits a retry only while the retry budget remains", () => {
    const policy = createAtlasApiRetryPolicy({
      maxRetries: 2
    });
    const error = httpError(503, "unavailable");

    expect(
      shouldRetryAtlasApiRequest({
        error,
        retryCount: 0,
        policy
      })
    ).toBe(true);

    expect(
      shouldRetryAtlasApiRequest({
        error,
        retryCount: 1,
        policy
      })
    ).toBe(true);

    expect(
      shouldRetryAtlasApiRequest({
        error,
        retryCount: 2,
        policy
      })
    ).toBe(false);
  });

  it("never retries a non-retryable error even when budget remains", () => {
    const policy = createAtlasApiRetryPolicy({
      maxRetries: 3
    });

    expect(
      shouldRetryAtlasApiRequest({
        error: httpError(401, "authentication"),
        retryCount: 0,
        policy
      })
    ).toBe(false);
  });

  it("calculates bounded exponential delays", () => {
    const policy = createAtlasApiRetryPolicy({
      maxRetries: 5,
      baseDelayMs: 100,
      maxDelayMs: 500
    });

    expect(atlasApiRetryDelayMs(0, policy)).toBe(100);
    expect(atlasApiRetryDelayMs(1, policy)).toBe(200);
    expect(atlasApiRetryDelayMs(2, policy)).toBe(400);
    expect(atlasApiRetryDelayMs(3, policy)).toBe(500);
    expect(atlasApiRetryDelayMs(4, policy)).toBe(500);
  });

  it("rejects an invalid retry count", () => {
    expect(() => atlasApiRetryDelayMs(-1)).toThrow(
      "Atlas API retry count must be a non-negative integer."
    );
  });
});
