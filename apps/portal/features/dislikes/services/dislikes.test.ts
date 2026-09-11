import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { createDislikeRecord, readDislikes, removeDislikeRecord } from "./dislikes";

const DISLIKE_ID = "dis_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function transportDislike() {
  return {
    schema_version: 1,
    dislike_id: DISLIKE_ID,
    user_id: USER_ID,
    provider: "jellyfin",
    item_id: "item-123",
    media_type: "movie",
    title: "Example Movie",
    metadata: {},
    created_at: "2026-08-09T12:00:00Z",
    updated_at: "2026-08-09T12:30:00Z"
  };
}

beforeEach(() => {
  authenticatedAtlasApiRequestMock.mockReset();
});

describe("Dislikes authenticated service boundary", () => {
  it("lists Dislikes through the self-scoped endpoint without transmitting a user ID", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      dislikes: [transportDislike()]
    });

    await expect(
      readDislikes({
        expectedUserId: USER_ID
      })
    ).resolves.toHaveLength(1);

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledOnce();

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe("/dislikes");
    expect(options).toMatchObject({
      method: "GET",
      cache: "no-store"
    });
    expect(options).not.toHaveProperty("body");
    expect(JSON.stringify(options)).not.toContain("user_id");
    expect(JSON.stringify(options)).not.toContain(USER_ID);
  });

  it("deletes by Dislike identity only and sends no caller-selected owner", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(transportDislike());

    await expect(
      removeDislikeRecord(DISLIKE_ID, {
        expectedUserId: USER_ID
      })
    ).resolves.toMatchObject({
      dislikeId: DISLIKE_ID,
      userId: USER_ID
    });

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledOnce();

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe(`/dislikes/${DISLIKE_ID}`);
    expect(options).toMatchObject({
      method: "DELETE",
      cache: "no-store"
    });
    expect(options).not.toHaveProperty("body");
    expect(JSON.stringify(options)).not.toContain("user_id");
    expect(JSON.stringify(options)).not.toContain(USER_ID);
  });

  it("fails closed when list ownership does not match the authenticated session", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      dislikes: [
        {
          ...transportDislike(),
          user_id: "usr_abcdef0123456789abcdef0123456789"
        }
      ]
    });

    await expect(
      readDislikes({
        expectedUserId: USER_ID
      })
    ).rejects.toThrow("Dislikes response crossed the authenticated-user boundary.");
  });

  it("fails closed when deletion returns a record owned by another user", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      ...transportDislike(),
      user_id: "usr_abcdef0123456789abcdef0123456789"
    });

    await expect(
      removeDislikeRecord(DISLIKE_ID, {
        expectedUserId: USER_ID
      })
    ).rejects.toThrow("Dislikes removal response crossed the authenticated-user boundary.");
  });
});

describe("createDislikeRecord", () => {
  it("creates one authenticated-user dislike without retrying the mutation", async () => {
    const userId = `usr_${"a".repeat(32)}`;
    const dislikeId = `dis_${"b".repeat(32)}`;

    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      schema_version: 1,
      dislike_id: dislikeId,
      user_id: userId,
      provider: "jellyfin",
      item_id: "jellyfin-item-123",
      media_type: "movie",
      title: "Interstellar",
      metadata: {},
      created_at: "2026-08-16T00:00:00Z",
      updated_at: "2026-08-16T00:00:00Z"
    });

    const dislike = await createDislikeRecord(
      {
        provider: " Jellyfin ",
        itemId: " jellyfin-item-123 "
      },
      {
        expectedUserId: userId
      }
    );

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/dislikes",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        retryPolicy: {
          maxRetries: 0,
          baseDelayMs: 250,
          maxDelayMs: 5_000
        },
        body: {
          provider: "jellyfin",
          item_id: "jellyfin-item-123"
        }
      })
    );

    expect(dislike.dislikeId).toBe(dislikeId);
    expect(dislike.userId).toBe(userId);
    expect(dislike.provider).toBe("jellyfin");
    expect(dislike.itemId).toBe("jellyfin-item-123");
  });

  it("rejects a dislike creation response that crosses the authenticated-user boundary", async () => {
    const expectedUserId = `usr_${"a".repeat(32)}`;
    const otherUserId = `usr_${"c".repeat(32)}`;

    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      schema_version: 1,
      dislike_id: `dis_${"b".repeat(32)}`,
      user_id: otherUserId,
      provider: "jellyfin",
      item_id: "jellyfin-item-123",
      media_type: "movie",
      title: "Interstellar",
      metadata: {},
      created_at: "2026-08-16T00:00:00Z",
      updated_at: "2026-08-16T00:00:00Z"
    });

    await expect(
      createDislikeRecord(
        {
          provider: "jellyfin",
          itemId: "jellyfin-item-123"
        },
        {
          expectedUserId
        }
      )
    ).rejects.toThrow("Dislike creation response crossed the authenticated-user boundary.");
  });

  it("rejects a dislike creation response for a different media identity", async () => {
    const userId = `usr_${"a".repeat(32)}`;

    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      schema_version: 1,
      dislike_id: `dis_${"b".repeat(32)}`,
      user_id: userId,
      provider: "jellyfin",
      item_id: "different-item",
      media_type: "movie",
      title: "Different item",
      metadata: {},
      created_at: "2026-08-16T00:00:00Z",
      updated_at: "2026-08-16T00:00:00Z"
    });

    await expect(
      createDislikeRecord(
        {
          provider: "jellyfin",
          itemId: "jellyfin-item-123"
        },
        {
          expectedUserId: userId
        }
      )
    ).rejects.toThrow("Dislike creation response did not match the requested media identity.");
  });
});
