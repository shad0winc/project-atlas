import { describe, expect, it } from "vitest";

import {
  createMediaSeriesDetail,
  createMediaSeriesSeason,
  mediaSeriesRequestType,
  type MediaSeriesDetail,
  type MediaSeriesSeason
} from "./series";

function season(overrides: Partial<MediaSeriesSeason> = {}): MediaSeriesSeason {
  return {
    seasonNumber: 1,
    name: "Season 1",
    episodeCount: 10,
    availability: "not_tracked" as const,
    requestabilityKnown: true,
    requestEligible: true,
    airDate: "2026-01-02",
    ...overrides
  };
}

function detail(overrides: Partial<MediaSeriesDetail> = {}): MediaSeriesDetail {
  return {
    providerMediaId: "1396",
    title: " Breaking Bad ",
    year: 2008,
    status: "ended" as const,
    inProduction: false,
    isOngoing: false,
    isAnime: false,
    availability: "not_tracked" as const,
    requestEligible: true,
    seasons: [season()],
    ...overrides
  };
}

describe("Media series Portal contracts", () => {
  it("normalizes one explicit requestable season", () => {
    expect(createMediaSeriesSeason(season())).toEqual({
      seasonNumber: 1,
      name: "Season 1",
      episodeCount: 10,
      availability: "not_tracked",
      requestabilityKnown: true,
      requestEligible: true,
      airDate: "2026-01-02"
    });
  });

  it("fails closed when unknown requestability is marked eligible", () => {
    expect(() =>
      createMediaSeriesSeason(
        season({
          requestabilityKnown: false,
          requestEligible: true
        })
      )
    ).toThrow("cannot be true when requestability is unknown");
  });

  it("rejects eligible tracked-unavailable season state", () => {
    expect(() =>
      createMediaSeriesSeason(
        season({
          availability: "available",
          requestEligible: true
        })
      )
    ).toThrow("conflicts with the season availability state");
  });

  it("sorts seasons and rejects duplicate season identity", () => {
    const normalized = createMediaSeriesDetail(
      detail({
        seasons: [season({ seasonNumber: 2, name: "Season 2" }), season()]
      })
    );

    expect(normalized.seasons.map((value) => value.seasonNumber)).toEqual([1, 2]);

    expect(() =>
      createMediaSeriesDetail(
        detail({
          seasons: [season(), season()]
        })
      )
    ).toThrow("unique season numbers");
  });

  it("requires whole-series eligibility to match not-tracked state", () => {
    expect(() =>
      createMediaSeriesDetail(
        detail({
          availability: "partially_available",
          requestEligible: true
        })
      )
    ).toThrow("requestEligible does not match");
  });

  it("requires ongoing metadata to match the lifecycle contract", () => {
    expect(() =>
      createMediaSeriesDetail(
        detail({
          status: "returning",
          isOngoing: false
        })
      )
    ).toThrow("isOngoing does not match");
  });

  it("uses server-provided anime classification for request type", () => {
    expect(mediaSeriesRequestType(createMediaSeriesDetail(detail()))).toBe("tv");

    expect(
      mediaSeriesRequestType(
        createMediaSeriesDetail(
          detail({
            isAnime: true
          })
        )
      )
    ).toBe("anime_tv");
  });

  it("rejects invalid TMDB identity and season zero", () => {
    expect(() =>
      createMediaSeriesDetail(
        detail({
          providerMediaId: "0"
        })
      )
    ).toThrow();

    expect(() =>
      createMediaSeriesSeason(
        season({
          seasonNumber: 0
        })
      )
    ).toThrow("positive integer");
  });
});
