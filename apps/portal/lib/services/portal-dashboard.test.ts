import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("./authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { readPortalDashboard } from "./portal-dashboard";

function dashboardEnvelope() {
  return {
    schema_version: 1,
    api_version: "v1",
    success: true,
    generated_at: "2026-08-29T00:00:00Z",
    data: {
      dashboard: {
        health: {
          status: "ok",
          service: "atlas-api",
          api_version: "v1"
        },
        operational: {
          generated_at: "2026-08-29T00:00:00Z",
          metrics: []
        },
        media: {
          generated_at: "2026-08-29T00:00:00Z",
          libraries: []
        },
        operations: {
          status: "unavailable",
          report: null,
          detail: null,
          summary: null,
          comparison: {
            status: "unavailable",
            score_delta: null,
            attention_delta: null,
            added_count: null,
            removed_count: null,
            changed_count: null,
            unchanged_count: null,
            difference_count: null,
            detail: null
          },
          recent_attention: []
        },
        scheduler: {
          status: "unavailable",
          detail: null,
          registered_count: null,
          enabled_count: null,
          disabled_count: null,
          due_count: null,
          running_count: null,
          failed_count: null,
          last_run_at: null,
          next_run_at: null,
          recent_failures: []
        }
      }
    }
  };
}

beforeEach(() => {
  authenticatedAtlasApiRequestMock.mockReset();
});

describe("Portal dashboard authenticated service boundary", () => {
  it("unwraps the public Atlas success envelope", async () => {
    const envelope = dashboardEnvelope();

    authenticatedAtlasApiRequestMock.mockResolvedValueOnce(envelope);

    await expect(readPortalDashboard()).resolves.toEqual(
      envelope.data
    );

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/portal/dashboard",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );
  });

  it("preserves the dashboard sections required by the Portal", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValueOnce(
      dashboardEnvelope()
    );

    const response = await readPortalDashboard();

    expect(response.dashboard).toEqual(
      expect.objectContaining({
        health: expect.any(Object),
        operational: expect.any(Object),
        media: expect.any(Object),
        operations: expect.any(Object),
        scheduler: expect.any(Object)
      })
    );
  });

  it("fails closed when the success flag is false", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      ...dashboardEnvelope(),
      success: false
    });

    await expect(readPortalDashboard()).rejects.toThrow(
      "Portal dashboard API returned an unsuccessful response."
    );
  });

  it("fails closed when dashboard data is absent", async () => {
    const envelope = dashboardEnvelope();

    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      ...envelope,
      data: {}
    });

    await expect(readPortalDashboard()).rejects.toThrow(
      "Portal dashboard API response is missing dashboard data."
    );
  });
});
