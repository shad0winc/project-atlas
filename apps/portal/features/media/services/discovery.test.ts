import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { readMediaDiscovery, searchMediaDiscovery } from "./discovery";

function transportItem(overrides: Record<string, unknown> = {}) {
  return {
    provider_media_id: "157336",
    media_type: "movie",
    title: "Interstellar",
    year: 2014,
    overview: "Space.",
    poster_path: "/poster.jpg",
    availability: "not_tracked",
    request_eligible: true,
    ...overrides
  };
}

function transportPage(overrides: Record<string, unknown> = {}) {
  return {
    items: [transportItem()],
    page: 1,
    total_pages: 3,
    next_page: 2,
    ...overrides
  };
}

beforeEach(() => {
  authenticatedAtlasApiRequestMock.mockReset();
});

describe("Media discovery authenticated service boundary", () => {
  it("loads one movie discovery page through the Atlas API only", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(
      transportPage({
        page: 2,
        total_pages: 4,
        next_page: 3
      })
    );

    await expect(
      readMediaDiscovery({
        mediaType: "movie",
        page: 2
      })
    ).resolves.toMatchObject({
      page: 2,
      totalPages: 4,
      nextPage: 3
    });

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe("/media/discover?media_type=movie&page=2");
    expect(options).toMatchObject({
      method: "GET",
      cache: "no-store"
    });
    expect(options).not.toHaveProperty("body");
  });

  it("normalizes and URL-encodes media search", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(transportPage());

    await searchMediaDiscovery({
      query: " Star Wars ",
      page: 1
    });

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe("/media/search?query=Star+Wars&page=1");
    expect(options).toMatchObject({
      method: "GET",
      cache: "no-store"
    });
    expect(options).not.toHaveProperty("body");
  });

  it("maps tracked provider state without changing eligibility", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(
      transportPage({
        items: [
          transportItem({
            availability: "available",
            request_eligible: false
          })
        ]
      })
    );

    const page = await readMediaDiscovery({
      mediaType: "movie"
    });

    expect(page.items[0]).toMatchObject({
      availability: "available",
      requestEligible: false
    });
  });

  it("fails closed when availability and eligibility disagree", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(
      transportPage({
        items: [
          transportItem({
            availability: "available",
            request_eligible: true
          })
        ]
      })
    );

    await expect(
      readMediaDiscovery({
        mediaType: "movie"
      })
    ).rejects.toThrow("requestEligible does not match");
  });

  it("fails closed when API next-page metadata disagrees with the domain model", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(
      transportPage({
        next_page: null
      })
    );

    await expect(
      readMediaDiscovery({
        mediaType: "movie"
      })
    ).rejects.toThrow("pagination did not match");
  });

  it("forwards an AbortSignal without exposing provider transport", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(transportPage());

    const controller = new AbortController();

    await readMediaDiscovery({
      mediaType: "tv",
      signal: controller.signal
    });

    const [, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(options).toMatchObject({
      signal: controller.signal
    });
  });
});
