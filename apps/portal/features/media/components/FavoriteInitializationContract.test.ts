import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

function source(relativePath: string): string {
  return readFileSync(
    resolve(process.cwd(), relativePath),
    "utf8"
  );
}

describe("existing Favorite initialization contract", () => {
  it("initializes the active Theater item from authenticated existing Favorites", () => {
    const theater = source(
      "app/(protected)/portal/theater/TheaterPageClient.tsx"
    );

    expect(theater).toContain(
      'import { loadFavorites } from "../../../../features/favorites";'
    );

    expect(theater).toContain("loadFavorites({");
    expect(theater).toContain("expectedUserId: user.user_id");

    expect(theater).toContain(
      "favorite.provider === session.provider"
    );

    expect(theater).toContain(
      "favorite.itemId === session.playableTargetId"
    );

    expect(theater).toMatch(
      /setFavoriteState\(\s*isFavorited\s*\?\s*"complete"\s*:\s*"idle"\s*\)/
    );
  });

  it("initializes Media Catalog Favorite identities from authenticated existing Favorites", () => {
    const catalog = source(
      "features/media/components/MediaCatalogView.tsx"
    );

    expect(catalog).toContain(
      'import { loadFavorites } from "../../favorites";'
    );

    expect(catalog).toContain("loadFavorites({");
    expect(catalog).toContain("expectedUserId: user.user_id");

    expect(catalog).toContain(
      "favorite.provider"
    );

    expect(catalog).toContain(
      "favorite.itemId"
    );

    expect(catalog).toContain(
      "setFavoritedItemIds"
    );
  });
});
