import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { readFavorites, removeFavoriteRecord } from "./favorites";

const FAVORITE_ID = "fav_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function transportFavorite() {
  return {
    schema_version: 1,
    favorite_id: FAVORITE_ID,
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

describe("Favorites authenticated service boundary", () => {
  it("lists Favorites through the self-scoped endpoint without transmitting a user ID", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      favorites: [transportFavorite()]
    });

    await expect(
      readFavorites({
        expectedUserId: USER_ID
      })
    ).resolves.toHaveLength(1);

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledOnce();

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe("/favorites");
    expect(options).toMatchObject({
      method: "GET",
      cache: "no-store"
    });
    expect(options).not.toHaveProperty("body");
    expect(JSON.stringify(options)).not.toContain("user_id");
    expect(JSON.stringify(options)).not.toContain(USER_ID);
  });

  it("deletes by Favorite identity only and sends no caller-selected owner", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(transportFavorite());

    await expect(
      removeFavoriteRecord(FAVORITE_ID, {
        expectedUserId: USER_ID
      })
    ).resolves.toMatchObject({
      favoriteId: FAVORITE_ID,
      userId: USER_ID
    });

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledOnce();

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe(`/favorites/${FAVORITE_ID}`);
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
      favorites: [
        {
          ...transportFavorite(),
          user_id: "usr_abcdef0123456789abcdef0123456789"
        }
      ]
    });

    await expect(
      readFavorites({
        expectedUserId: USER_ID
      })
    ).rejects.toThrow("Favorites response crossed the authenticated-user boundary.");
  });

  it("fails closed when deletion returns a record owned by another user", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      ...transportFavorite(),
      user_id: "usr_abcdef0123456789abcdef0123456789"
    });

    await expect(
      removeFavoriteRecord(FAVORITE_ID, {
        expectedUserId: USER_ID
      })
    ).rejects.toThrow("Favorites removal response crossed the authenticated-user boundary.");
  });
});
