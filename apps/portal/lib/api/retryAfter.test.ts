import { describe, expect, it } from "vitest";
import { parseAtlasRetryAfter } from "./retryAfter";

describe("Retry-After header", () => {
  it("reads integer seconds including zero", () => {
    expect(parseAtlasRetryAfter("10")).toBe(10);
    expect(parseAtlasRetryAfter("0")).toBe(0);
  });
  it("reads an HTTP date against the supplied clock", () => {
    expect(parseAtlasRetryAfter("Fri, 30 Oct 2026 22:00:10 GMT", Date.parse("2026-10-30T22:00:00Z"))).toBe(10);
  });
  it.each([null, "", "invalid", "-5", "999999999999999999999", "3601"])("rejects an absent or unsafe value: %s", value => {
    expect(parseAtlasRetryAfter(value)).toBeNull();
  });
});

it("preserves Retry-After on the actual HTTP error", async () => {
  const { performAtlasApiRequest } = await import("./request");
  const { AtlasApiError } = await import("./errors");
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "fixture" }), {
    status: 429, headers: { "Content-Type": "application/json", "Retry-After": "10" },
  });
  try {
    await expect(performAtlasApiRequest("/sports/events")).rejects.toMatchObject({
      status: 429, retryAfterSeconds: 10,
    });
    expect(new AtlasApiError({ status: 429, detail: "fixture", method: "GET", path: "/sports/events",
      requestId: "fixture", kind: "rate-limit" }).retryAfterSeconds).toBeNull();
  } finally { globalThis.fetch = original; }
});
