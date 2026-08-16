import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { readMediaCatalog } from "./catalog";

describe("Media catalog authenticated service boundary", () => {
  beforeEach(() => {
    authenticatedAtlasApiRequestMock.mockReset();
  });

  it("loads one bounded Jellyfin catalog page", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      provider: "jellyfin",
      page: 1,
      page_size: 24,
      total: 1,
      items: [
        {
          provider: "jellyfin",
          item_id: "jf-interstellar",
          media_type: "movie",
          title: "Interstellar",
          year: 2014,
          library: "Movies"
        }
      ]
    });

    const page = await readMediaCatalog({
      page: 1,
      pageSize: 24
    });

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledOnce();

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/media/catalog?page=1&page_size=24",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );

    expect(page).toEqual({
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
    });
  });

  it("rejects an API page whose item provider crosses the catalog boundary", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      provider: "jellyfin",
      page: 1,
      page_size: 24,
      total: 1,
      items: [
        {
          provider: "tmdb",
          item_id: "157336",
          media_type: "movie",
          title: "Interstellar",
          year: 2014,
          library: null
        }
      ]
    });

    await expect(readMediaCatalog()).rejects.toThrow(
      "Catalog item provider did not match the catalog provider."
    );
  });

  it("rejects invalid local page size before transport", async () => {
    await expect(
      readMediaCatalog({
        pageSize: 101
      })
    ).rejects.toThrow("catalog.pageSize must be between 1 and 100.");

    expect(authenticatedAtlasApiRequestMock).not.toHaveBeenCalled();
  });
});
