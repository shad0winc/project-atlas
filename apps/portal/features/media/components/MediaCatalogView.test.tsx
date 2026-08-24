import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { MediaCatalogContent } from "./MediaCatalogView";

const page = {
  provider: "jellyfin",
  page: 1,
  pageSize: 24,
  total: 1,
  items: [
    {
      provider: "jellyfin",
      itemId: "jf-interstellar",
      mediaType: "movie",
      title: "Interstellar",
      year: 2014,
      library: "Movies"
    }
  ]
} as const;

describe("MediaCatalogContent", () => {
  it("renders genuine Jellyfin catalog identity with Favorite control", () => {
    const markup = renderToStaticMarkup(
      <MediaCatalogContent
        canFavorite
        error={null}
        favoritedItemIds={new Set()}
        favoritingItemId={null}
        loading={false}
        onFavorite={vi.fn()}
        onRetry={vi.fn()}
        page={page}
      />
    );

    expect(markup).toContain('aria-label="Your Jellyfin library"');

    expect(markup).toContain("Interstellar");

    expect(markup).toContain("Library: Movies");

    expect(markup).toContain('aria-label="Add Interstellar to favorites"');
  });

  it("withholds mutation control from read-only users", () => {
    const markup = renderToStaticMarkup(
      <MediaCatalogContent
        canFavorite={false}
        error={null}
        favoritedItemIds={new Set()}
        favoritingItemId={null}
        loading={false}
        onFavorite={vi.fn()}
        onRetry={vi.fn()}
        page={page}
      />
    );

    expect(markup).not.toContain("Add to favorites");

    expect(markup).toContain("cannot modify Favorites");
  });

  it("renders the completed Favorite state", () => {
    const markup = renderToStaticMarkup(
      <MediaCatalogContent
        canFavorite
        error={null}
        favoritedItemIds={new Set(["jellyfin\u0000jf-interstellar"])}
        favoritingItemId={null}
        loading={false}
        onFavorite={vi.fn()}
        onRetry={vi.fn()}
        page={page}
      />
    );

    expect(markup).toContain("Added to favorites");

    expect(markup).toContain('disabled=""');
  });
});
