import { describe, expect, it } from "vitest";

import {
  createDislike,
  createDislikeCollection,
  createDislikesState,
  type Dislike
} from "./dislikes";

const DISLIKE_ID = "dis_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function dislike(overrides: Partial<Dislike> = {}): Dislike {
  return {
    schemaVersion: 1,
    dislikeId: DISLIKE_ID,
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

describe("Dislikes domain contract", () => {
  it("normalizes identity, provider, media type, title, and timestamps", () => {
    expect(createDislike(dislike())).toEqual({
      schemaVersion: 1,
      dislikeId: DISLIKE_ID,
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

  it("rejects malformed Dislike and user identities", () => {
    expect(() =>
      createDislike(
        dislike({
          dislikeId: "dislike-1"
        })
      )
    ).toThrow("dislike.dislikeId is invalid.");

    expect(() =>
      createDislike(
        dislike({
          userId: "user-1"
        })
      )
    ).toThrow("dislike.userId is invalid.");
  });

  it("rejects invalid timestamps", () => {
    expect(() =>
      createDislike(
        dislike({
          createdAt: "not-a-time"
        })
      )
    ).toThrow("dislike.createdAt must be a valid timestamp.");
  });

  it("rejects duplicate Dislike identities", () => {
    expect(() => createDislikeCollection([dislike(), dislike()])).toThrow(
      "Dislike IDs must be unique."
    );
  });

  it("fails closed when a collection crosses the expected user boundary", () => {
    expect(() =>
      createDislikeCollection(
        [
          dislike(),
          dislike({
            dislikeId: "dis_abcdef0123456789abcdef0123456789",
            userId: "usr_abcdef0123456789abcdef0123456789",
            itemId: "item-456"
          })
        ],
        USER_ID
      )
    ).toThrow("Dislikes response crossed the authenticated-user boundary.");
  });

  it("distinguishes loading, ready-empty, and error states", () => {
    expect(createDislikesState(null, null)).toEqual({
      status: "loading"
    });

    expect(createDislikesState([], null)).toEqual({
      status: "ready",
      data: []
    });

    expect(createDislikesState(null, new Error("Unavailable"))).toMatchObject({
      status: "error"
    });
  });
});
