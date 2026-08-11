import { describe, expect, it } from "vitest";

import {
  createFavorite,
  createFavoriteCollection,
  createFavoritesState,
  type Favorite
} from "./favorites";

const FAVORITE_ID = "fav_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function favorite(overrides: Partial<Favorite> = {}): Favorite {
  return {
    schemaVersion: 1,
    favoriteId: FAVORITE_ID,
    userId: USER_ID,
    provider: " Jellyfin ",
    itemId: " item-123 ",
    mediaType: " Movie ",
    title: " Example Movie ",
    metadata: {
      source: "test"
    },
    createdAt: "2026-08-09T12:00:00Z",
    updatedAt: "2026-08-09T12:30:00Z",
    ...overrides
  };
}

describe("Favorites domain contract", () => {
  it("normalizes identity, provider, media type, title, and timestamps", () => {
    expect(createFavorite(favorite())).toEqual({
      schemaVersion: 1,
      favoriteId: FAVORITE_ID,
      userId: USER_ID,
      provider: "jellyfin",
      itemId: "item-123",
      mediaType: "movie",
      title: "Example Movie",
      metadata: {
        source: "test"
      },
      createdAt: "2026-08-09T12:00:00.000Z",
      updatedAt: "2026-08-09T12:30:00.000Z"
    });
  });

  it("rejects malformed Favorite and user identities", () => {
    expect(() =>
      createFavorite(
        favorite({
          favoriteId: "favorite-1"
        })
      )
    ).toThrow("favorite.favoriteId is invalid.");

    expect(() =>
      createFavorite(
        favorite({
          userId: "user-1"
        })
      )
    ).toThrow("favorite.userId is invalid.");
  });

  it("rejects invalid timestamps", () => {
    expect(() =>
      createFavorite(
        favorite({
          createdAt: "not-a-time"
        })
      )
    ).toThrow("favorite.createdAt must be a valid timestamp.");
  });

  it("rejects duplicate Favorite identities", () => {
    expect(() => createFavoriteCollection([favorite(), favorite()])).toThrow(
      "Favorite IDs must be unique."
    );
  });

  it("fails closed when a collection crosses the expected user boundary", () => {
    expect(() =>
      createFavoriteCollection(
        [
          favorite(),
          favorite({
            favoriteId: "fav_abcdef0123456789abcdef0123456789",
            userId: "usr_abcdef0123456789abcdef0123456789",
            itemId: "item-456"
          })
        ],
        USER_ID
      )
    ).toThrow("Favorites response crossed the authenticated-user boundary.");
  });

  it("distinguishes loading, ready-empty, and error states", () => {
    expect(createFavoritesState(null, null)).toEqual({
      status: "loading"
    });

    expect(createFavoritesState([], null)).toEqual({
      status: "ready",
      data: []
    });

    expect(createFavoritesState(null, new Error("Unavailable"))).toMatchObject({
      status: "error"
    });
  });
});
