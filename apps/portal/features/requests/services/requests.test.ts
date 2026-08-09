import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { RequestCancellationError, cancelRequestRecord, readRequests } from "./requests";

const REQUEST_ID = "req_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function transportRequest(overrides: Record<string, unknown> = {}) {
  return {
    request_id: REQUEST_ID,
    user_id: USER_ID,
    media_type: "movie",
    provider: "jellyseerr",
    provider_media_id: "157336",
    title: "Interstellar",
    year: 2014,
    season_number: null,
    status: "approved",
    terminal: false,
    active: true,
    can_cancel: true,
    recovery_required: false,
    created_at: "2026-08-09T12:00:00Z",
    updated_at: "2026-08-09T12:30:00Z",
    available_at: null,
    ...overrides
  };
}

beforeEach(() => {
  authenticatedAtlasApiRequestMock.mockReset();
});

describe("Personal Requests authenticated service boundary", () => {
  it("lists through the self-scoped endpoint without transmitting a user ID", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      requests: [transportRequest()]
    });

    await expect(
      readRequests({
        expectedUserId: USER_ID
      })
    ).resolves.toHaveLength(1);

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe("/requests");
    expect(options).toMatchObject({
      method: "GET",
      cache: "no-store"
    });
    expect(options).not.toHaveProperty("body");
    expect(JSON.stringify(options)).not.toContain("user_id");
    expect(JSON.stringify(options)).not.toContain(USER_ID);
  });

  it("fails closed when list ownership crosses the authenticated session", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      requests: [
        transportRequest({
          user_id: "usr_abcdef0123456789abcdef0123456789"
        })
      ]
    });

    await expect(
      readRequests({
        expectedUserId: USER_ID
      })
    ).rejects.toThrow("Media Requests response crossed the authenticated-user boundary.");
  });

  it("cancels by Atlas Request identity only and explicitly disables transport retries", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(
      transportRequest({
        status: "cancelled",
        terminal: true,
        active: false,
        can_cancel: false,
        updated_at: "2026-08-09T13:00:00Z"
      })
    );

    await expect(
      cancelRequestRecord(REQUEST_ID, {
        expectedUserId: USER_ID
      })
    ).resolves.toMatchObject({
      requestId: REQUEST_ID,
      userId: USER_ID,
      status: "cancelled"
    });

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe(`/requests/${REQUEST_ID}/cancel`);

    expect(options).toMatchObject({
      method: "POST",
      cache: "no-store",
      retryPolicy: {
        maxRetries: 0
      }
    });

    expect(options).not.toHaveProperty("body");
    expect(JSON.stringify(options)).not.toContain("user_id");
    expect(JSON.stringify(options)).not.toContain(USER_ID);
  });

  it("fails closed when cancellation returns another user's Request", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(
      transportRequest({
        user_id: "usr_abcdef0123456789abcdef0123456789",
        status: "cancelled",
        terminal: true,
        active: false,
        can_cancel: false
      })
    );

    await expect(
      cancelRequestRecord(REQUEST_ID, {
        expectedUserId: USER_ID
      })
    ).rejects.toThrow("Cancellation response crossed the authenticated-user boundary.");
  });

  it("preserves the API reconciliation warning and Do-not-retry contract", async () => {
    authenticatedAtlasApiRequestMock.mockRejectedValue({
      status: 409,
      detail: "Media request cancellation requires reconciliation. Do not retry this request."
    });

    let caught: unknown;

    try {
      await cancelRequestRecord(REQUEST_ID, {
        expectedUserId: USER_ID
      });
    } catch (error: unknown) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(RequestCancellationError);

    expect((caught as RequestCancellationError).reconciliationRequired).toBe(true);

    expect((caught as Error).message).toContain("Do not retry this request.");
  });

  it("requires a safe refresh before retry after any failed cancellation", async () => {
    authenticatedAtlasApiRequestMock.mockRejectedValue(new Error("Network unavailable."));

    await expect(
      cancelRequestRecord(REQUEST_ID, {
        expectedUserId: USER_ID
      })
    ).rejects.toThrow("Refresh request status before attempting another cancellation.");
  });
});
