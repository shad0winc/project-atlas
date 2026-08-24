import { describe, expect, it } from "vitest";

import { createMediaCatalogItem, createMediaCatalogPage } from "./catalog";

describe("Media catalog domain model", () => {
  it("normalizes one genuine provider media identity", () => {
    expect(
      createMediaCatalogItem({
        provider: " Jellyfin ",
        itemId: " jf-interstellar ",
        mediaType: " Movie ",
        title: " Interstellar ",
        year: 2014,
        library: " Movies "
      })
    ).toEqual({
      provider: "jellyfin",
      itemId: "jf-interstellar",
      mediaType: "movie",
      title: "Interstellar",
      year: 2014,
      library: "Movies"
    });
  });

  it("rejects duplicate provider item identities", () => {
    expect(() =>
      createMediaCatalogPage({
        provider: "jellyfin",
        page: 1,
        pageSize: 24,
        total: 2,
        items: [
          {
            provider: "jellyfin",
            itemId: "same-item",
            mediaType: "movie",
            title: "One"
          },
          {
            provider: "jellyfin",
            itemId: "same-item",
            mediaType: "movie",
            title: "Two"
          }
        ]
      })
    ).toThrow("Media catalog identities must be unique within a page.");
  });

  it("rejects cross-provider page contents", () => {
    expect(() =>
      createMediaCatalogPage({
        provider: "jellyfin",
        page: 1,
        pageSize: 24,
        total: 1,
        items: [
          {
            provider: "tmdb",
            itemId: "157336",
            mediaType: "movie",
            title: "Interstellar"
          }
        ]
      })
    ).toThrow("Catalog item provider did not match the catalog provider.");
  });

  it("rejects invalid pagination contracts", () => {
    expect(() =>
      createMediaCatalogPage({
        provider: "jellyfin",
        page: 0,
        pageSize: 24,
        total: 0,
        items: []
      })
    ).toThrow("catalog.page must be a positive integer.");
  });
});
