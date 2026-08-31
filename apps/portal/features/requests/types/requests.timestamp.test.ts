import { describe, expect, it } from "vitest";

import { createMediaRequest } from "./requests";

const baseRequest = {
  requestId: "req_0123456789abcdef0123456789abcdef",
  userId: "usr_0123456789abcdef0123456789abcdef",
  mediaType: "movie" as const,
  provider: "jellyseerr",
  providerMediaId: "123",
  title: "Example",
  status: "approved" as const,
  terminal: false,
  active: true,
  canCancel: true,
  recoveryRequired: false,
  createdAt: "2026-08-13T02:04:58.832861Z",
  updatedAt: "2026-08-13T02:04:58Z"
};

describe("request timestamp precision", () => {
  it("repairs provider whole-second precision loss", () => {
    const request = createMediaRequest(baseRequest);
    expect(request.updatedAt).toBe(request.createdAt);
  });

  it("still rejects a genuinely earlier update", () => {
    expect(() =>
      createMediaRequest({
        ...baseRequest,
        updatedAt: "2026-08-13T02:04:56Z"
      })
    ).toThrow("request.updatedAt cannot be earlier than request.createdAt.");
  });
});
