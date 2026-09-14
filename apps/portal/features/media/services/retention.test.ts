import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { readMediaRetention } from "./retention";

describe("media retention authenticated service boundary", () => {
  beforeEach(() => {
    authenticatedAtlasApiRequestMock.mockReset();
  });

  it("reads one authoritative retention record through the media endpoint", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      provider: "jellyfin",
      item_id: "item-123",
      eligible: false,
      retained: true,
      lifecycle: {
        state: "scheduled",
        rule: "unwatched_30d",
        basis_at: "2026-08-15T00:00:00Z",
        delete_at: "2026-09-14T00:00:00Z"
      }
    });

    const result = await readMediaRetention(
      "jellyfin",
      "item-123"
    );

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledTimes(1);

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/media/jellyfin/item-123/retention",
      expect.objectContaining({
        method: "GET"
      })
    );

    expect(result).toEqual({
      provider: "jellyfin",
      itemId: "item-123",
      eligible: false,
      retained: true,
      lifecycle: {
        state: "scheduled",
        rule: "unwatched_30d",
        basisAt: "2026-08-15T00:00:00Z",
        deleteAt: "2026-09-14T00:00:00Z"
      }
    });
  });

  it("URL-encodes provider and item identity", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      provider: "jellyfin",
      item_id: "ABC/123",
      eligible: false,
      retained: true,
      lifecycle: {
        state: "unknown",
        rule: "unavailable",
        basis_at: null,
        delete_at: null
      }
    });

    await readMediaRetention(
      "jellyfin",
      "ABC/123"
    );

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/media/jellyfin/ABC%2F123/retention",
      expect.objectContaining({
        method: "GET"
      })
    );
  });

  it("rejects a response for a different media identity", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      provider: "jellyfin",
      item_id: "different-item",
      eligible: false,
      retained: true,
      lifecycle: {
        state: "unknown",
        rule: "unavailable",
        basis_at: null,
        delete_at: null
      }
    });

    await expect(
      readMediaRetention(
        "jellyfin",
        "requested-item"
      )
    ).rejects.toThrow(
      "Media retention response did not match the requested media identity."
    );
  });

  it("accepts provider case normalization but keeps item identity exact", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      provider: "jellyfin",
      item_id: "ABC-123",
      eligible: false,
      retained: true,
      lifecycle: {
        state: "unknown",
        rule: "unavailable",
        basis_at: null,
        delete_at: null
      }
    });

    const result = await readMediaRetention(
      "JELLYFIN",
      "ABC-123"
    );

    expect(result.provider).toBe("jellyfin");
    expect(result.itemId).toBe("ABC-123");
  });

  it("passes AbortSignal through the authenticated request boundary", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      provider: "jellyfin",
      item_id: "item-123",
      eligible: false,
      retained: true,
      lifecycle: {
        state: "unknown",
        rule: "unavailable",
        basis_at: null,
        delete_at: null
      }
    });

    const controller = new AbortController();

    await readMediaRetention(
      "jellyfin",
      "item-123",
      controller.signal
    );

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/media/jellyfin/item-123/retention",
      expect.objectContaining({
        method: "GET",
        signal: controller.signal
      })
    );
  });
});
