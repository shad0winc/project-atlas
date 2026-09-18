import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { MediaCatalogPage } from "../types/catalog";

const { watchActionPropsMock } = vi.hoisted(() => ({
  watchActionPropsMock: vi.fn()
}));

vi.mock("../../playback/components/WatchAction", () => ({
  WatchAction: (props: {
    provider: string;
    itemId: string;
  }) => {
    watchActionPropsMock(props);

    return (
      <a data-testid="generic-watch-action">
        Watch Now
      </a>
    );
  }
}));

vi.mock("../../dislikes", () => ({
  DislikeAction: () => null
}));

import { MediaCatalogContent } from "./MediaCatalogView";

function page(
  mediaType: string,
  itemId: string,
  title: string
): MediaCatalogPage {
  return {
    provider: "jellyfin",
    page: 1,
    pageSize: 24,
    total: 1,
    items: [
      {
        provider: "jellyfin",
        itemId,
        mediaType,
        title,
        library: "Library"
      }
    ]
  } as unknown as MediaCatalogPage;
}

function renderCatalog(
  catalog: MediaCatalogPage
): string {
  return renderToStaticMarkup(
    <MediaCatalogContent
      canFavorite={false}
      error={null}
      favoritedItemIds={new Set()}
      favoritingItemId={null}
      loading={false}
      onFavorite={vi.fn()}
      onRetry={vi.fn()}
      page={catalog}
    />
  );
}

describe(
  "MediaCatalogView TV/Anime episode navigation contract",
  () => {
    it(
      "preserves direct Watch Now for movie library items",
      () => {
        watchActionPropsMock.mockClear();

        const markup = renderCatalog(
          page(
            "movie",
            "movie-1",
            "Example Movie"
          )
        );

        expect(
          watchActionPropsMock
        ).toHaveBeenCalledTimes(1);

        expect(
          watchActionPropsMock
        ).toHaveBeenCalledWith({
          provider: "jellyfin",
          itemId: "movie-1"
        });

        expect(markup).toContain(
          "Watch Now"
        );
      }
    );

    it.each([
      ["tv", "series-1", "Example Series"],
      [
        "anime_tv",
        "anime-series-1",
        "Example Anime"
      ]
    ])(
      "requires explicit episode navigation for %s library items",
      (
        mediaType,
        itemId,
        title
      ) => {
        watchActionPropsMock.mockClear();

        const markup = renderCatalog(
          page(
            mediaType,
            itemId,
            title
          )
        );

        expect(
          watchActionPropsMock
        ).not.toHaveBeenCalled();

        expect(markup).toContain(
          "View episodes"
        );

        expect(markup).not.toContain(
          "Watch Now"
        );
      }
    );
  }
);
