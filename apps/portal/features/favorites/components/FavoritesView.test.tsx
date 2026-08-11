import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { createFavorite, type Favorite } from "../types/favorites";

import { FavoritesContent } from "./FavoritesView";

const FAVORITE_ID = "fav_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function favorite(overrides: Partial<Favorite> = {}): Favorite {
  return createFavorite({
    schemaVersion: 1,
    favoriteId: FAVORITE_ID,
    userId: USER_ID,
    provider: "jellyfin",
    itemId: "item-123",
    mediaType: "movie",
    title: "Example Movie",
    metadata: {},
    createdAt: "2026-08-09T12:00:00Z",
    updatedAt: "2026-08-09T12:30:00Z",
    ...overrides
  });
}

const callbacks = {
  onRetry: () => undefined,
  onBeginRemoval: () => undefined,
  onCancelRemoval: () => undefined,
  onConfirmRemoval: () => undefined
};

describe("Favorites presentation", () => {
  it("renders accessible loading content", () => {
    const markup = renderToStaticMarkup(
      <FavoritesContent
        {...callbacks}
        canRemove={true}
        mutationError={null}
        pendingRemovalId={null}
        removingFavoriteId={null}
        state={{
          status: "loading"
        }}
      />
    );

    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain('aria-label="Loading favorites"');
  });

  it("renders an actionable load error", () => {
    const markup = renderToStaticMarkup(
      <FavoritesContent
        {...callbacks}
        canRemove={true}
        mutationError={null}
        pendingRemovalId={null}
        removingFavoriteId={null}
        state={{
          status: "error",
          error: new Error("Favorites request failed.")
        }}
      />
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Favorites request failed.");
    expect(markup).toContain("Try again");
  });

  it("renders a successful empty list distinctly from an error", () => {
    const markup = renderToStaticMarkup(
      <FavoritesContent
        {...callbacks}
        canRemove={true}
        mutationError={null}
        pendingRemovalId={null}
        removingFavoriteId={null}
        state={{
          status: "ready",
          data: []
        }}
      />
    );

    expect(markup).toContain("Your Favorites list is empty");
    expect(markup).not.toContain('role="alert"');
  });

  it("shows saved media while withholding removal controls from read-only users", () => {
    const markup = renderToStaticMarkup(
      <FavoritesContent
        {...callbacks}
        canRemove={false}
        mutationError={null}
        pendingRemovalId={null}
        removingFavoriteId={null}
        state={{
          status: "ready",
          data: [favorite()]
        }}
      />
    );

    expect(markup).toContain("Example Movie");
    expect(markup).toContain("Jellyfin");
    expect(markup).toContain("Read-only access");
    expect(markup).not.toContain("Remove from favorites");
  });

  it("exposes removal only when write permission is available", () => {
    const markup = renderToStaticMarkup(
      <FavoritesContent
        {...callbacks}
        canRemove={true}
        mutationError={null}
        pendingRemovalId={null}
        removingFavoriteId={null}
        state={{
          status: "ready",
          data: [favorite()]
        }}
      />
    );

    expect(markup).toContain("Remove from favorites");
    expect(markup).not.toContain("Confirm removal");
  });

  it("requires an explicit second action before removal", () => {
    const markup = renderToStaticMarkup(
      <FavoritesContent
        {...callbacks}
        canRemove={true}
        mutationError={null}
        pendingRemovalId={FAVORITE_ID}
        removingFavoriteId={null}
        state={{
          status: "ready",
          data: [favorite()]
        }}
      />
    );

    expect(markup).toContain("Confirm removal");
    expect(markup).toContain("Keep favorite");
  });

  it("surfaces mutation failures without discarding the loaded list", () => {
    const markup = renderToStaticMarkup(
      <FavoritesContent
        {...callbacks}
        canRemove={true}
        mutationError={new Error("Removal failed.")}
        pendingRemovalId={FAVORITE_ID}
        removingFavoriteId={null}
        state={{
          status: "ready",
          data: [favorite()]
        }}
      />
    );

    expect(markup).toContain("Favorite could not be removed");
    expect(markup).toContain("Removal failed.");
    expect(markup).toContain("Example Movie");
  });
});
