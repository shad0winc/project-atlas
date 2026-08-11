import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { readMediaSeriesDetail } from "./series";

function transport(overrides: Record<string, unknown> = {}) {
  return {
    provider_media_id: "1396",
    title: "Breaking Bad",
    year: 2008,
    overview: "Chemistry.",
    poster_path: "/poster.jpg",
    status: "ended",
    in_production: false,
    is_ongoing: false,
    is_anime: false,
    availability: "partially_available",
    request_eligible: false,
    seasons: [
      {
        season_number: 1,
        name: "Season 1",
        episode_count: 7,
        availability: "available",
        requestability_known: true,
        request_eligible: false,
        air_date: "2008-01-20"
      },
      {
        season_number: 2,
        name: "Season 2",
        episode_count: 13,
        availability: "unknown",
        requestability_known: true,
        request_eligible: true,
        air_date: "2009-03-08"
      }
    ],
    ...overrides
  };
}

beforeEach(() => {
  authenticatedAtlasApiRequestMock.mockReset();
});

describe("Media series authenticated service boundary", () => {
  it("loads TV detail through the Atlas API only", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(transport());

    const detail = await readMediaSeriesDetail({
      providerMediaId: "1396"
    });

    expect(detail.seasons[1]).toMatchObject({
      seasonNumber: 2,
      availability: "unknown",
      requestabilityKnown: true,
      requestEligible: true
    });

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe("/media/tv/1396");
    expect(options).toMatchObject({
      method: "GET",
      cache: "no-store"
    });
    expect(options).not.toHaveProperty("body");
  });

  it("forwards AbortSignal", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(transport());
    const controller = new AbortController();

    await readMediaSeriesDetail({
      providerMediaId: "1396",
      signal: controller.signal
    });

    const [, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];
    expect(options).toMatchObject({ signal: controller.signal });
  });

  it("requires positive provider identity before HTTP", async () => {
    await expect(
      readMediaSeriesDetail({
        providerMediaId: "0"
      })
    ).rejects.toThrow();

    expect(authenticatedAtlasApiRequestMock).not.toHaveBeenCalled();
  });

  it("rejects provider identity mismatch", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(
      transport({
        provider_media_id: "1397"
      })
    );

    await expect(
      readMediaSeriesDetail({
        providerMediaId: "1396"
      })
    ).rejects.toThrow("identity did not match");
  });

  it("fails closed when season requestability is inconsistent", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(
      transport({
        seasons: [
          {
            season_number: 2,
            name: "Season 2",
            episode_count: 13,
            availability: "available",
            requestability_known: true,
            request_eligible: true,
            air_date: null
          }
        ]
      })
    );

    await expect(
      readMediaSeriesDetail({
        providerMediaId: "1396"
      })
    ).rejects.toThrow("conflicts with the season availability state");
  });
});
