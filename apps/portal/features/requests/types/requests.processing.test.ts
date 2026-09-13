import { describe, expect, it } from "vitest";

import {
  createMediaRequest
} from "./requests";

const REQUEST_ID = "req_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

describe("Request processing lifecycle domain", () => {
  it("accepts processing as a first-class Atlas request status", () => {
    const request = createMediaRequest({
      requestId: REQUEST_ID,
      userId: USER_ID,
      mediaType: "movie",
      provider: "jellyseerr",
      providerMediaId: "157336",
      title: "Interstellar",
      year: 2014,
      status: "processing",
      terminal: false,
      active: true,
      canCancel: true,
      recoveryRequired: false,
      createdAt: "2026-09-13T04:00:00Z",
      updatedAt: "2026-09-13T04:40:00Z"
    });

    expect(request.status).toBe("processing");
    expect(request.terminal).toBe(false);
    expect(request.active).toBe(true);
  });
});
