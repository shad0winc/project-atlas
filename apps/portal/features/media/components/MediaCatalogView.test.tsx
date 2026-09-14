import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const { dislikePropsMock } = vi.hoisted(() => ({
  dislikePropsMock: vi.fn()
}));

vi.mock("../../dislikes", () => ({
  DislikeAction: (props: {
    provider: string;
    itemId: string;
    expectedUserId: string;
    title?: string;
    onDisliked?: () => void | Promise<void>;
  }) => {
    dislikePropsMock(props);

    return (
      <span data-testid="dislike-action">
        Dislike
      </span>
    );
  }
}));

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

  it("renders authoritative retention state supplied for a catalog item", () => {
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
        retentionByItemId={
          new Map([
            [
              "jellyfin\u0000jf-interstellar",
              {
                provider: "jellyfin",
                itemId: "jf-interstellar",
                eligible: false,
                retained: true,
                lifecycle: {
                  state: "scheduled",
                  rule: "unwatched_30d",
                  basisAt: "2026-08-15T12:00:00Z",
                  deleteAt: "2026-09-14T12:00:00Z"
                }
              }
            ]
          ])
        }
      />
    );

    expect(markup).toContain("Scheduled for deletion");
    expect(markup).toContain("2026-09-14T12:00:00Z");
  });

  it("passes an item-scoped Dislike success callback to the rendered mutation control", () => {
    dislikePropsMock.mockClear();

    const onDisliked = vi.fn();

    renderToStaticMarkup(
      <MediaCatalogContent
        canDislike
        canFavorite
        dislikeExpectedUserId="usr_0123456789abcdef0123456789abcdef"
        error={null}
        favoritedItemIds={new Set()}
        favoritingItemId={null}
        loading={false}
        onDisliked={onDisliked}
        onFavorite={vi.fn()}
        onRetry={vi.fn()}
        page={page}
      />
    );

    expect(dislikePropsMock).toHaveBeenCalledTimes(1);

    const props =
      dislikePropsMock.mock.calls[0]?.[0];

    expect(props).toMatchObject({
      provider: "jellyfin",
      itemId: "jf-interstellar"
    });

    expect(props.onDisliked).toBeTypeOf("function");
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
