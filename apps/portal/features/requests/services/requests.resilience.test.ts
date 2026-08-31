import { beforeEach, describe, expect, it, vi } from "vitest";

import { readRequests } from "./requests";

const { authenticatedRequestMock } = vi.hoisted(() => ({
  authenticatedRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedRequestMock
}));

const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function responseRequest(overrides: Record<string, unknown> = {}) {
  return {
    request_id: "req_0123456789abcdef0123456789abcdef",
    user_id: USER_ID,
    media_type: "movie",
    provider: "jellyseerr",
    provider_media_id: "123",
    title: "Example",
    year: null,
    season_number: null,
    status: "approved",
    terminal: false,
    active: true,
    can_cancel: true,
    recovery_required: false,
    created_at: "2026-08-13T02:04:58.832861Z",
    updated_at: "2026-08-13T02:04:58Z",
    available_at: null,
    ...overrides
  };
}

describe("request collection resilience", () => {
  beforeEach(() => {
    authenticatedRequestMock.mockReset();
  });

  it("keeps healthy records when one legacy record is malformed", async () => {
    authenticatedRequestMock.mockResolvedValue({
      requests: [
        responseRequest(),
        responseRequest({
          request_id: "req_abcdef0123456789abcdef0123456789",
          updated_at: "2026-08-13T02:04:50Z"
        })
      ]
    });

    const requests = await readRequests({
      expectedUserId: USER_ID
    });

    expect(requests).toHaveLength(1);
    expect(requests[0]?.requestId).toBe(
      "req_0123456789abcdef0123456789abcdef"
    );
  });

  it("still fails closed on an owner-boundary violation", async () => {
    authenticatedRequestMock.mockResolvedValue({
      requests: [
        responseRequest({
          user_id: "usr_abcdef0123456789abcdef0123456789"
        })
      ]
    });

    await expect(
      readRequests({
        expectedUserId: USER_ID
      })
    ).rejects.toThrow(
      "Media Requests response crossed the authenticated-user boundary."
    );
  });
});
