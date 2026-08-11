import { describe, expect, it } from "vitest";

import {
  createMediaDiscoveryItem,
  createMediaDiscoveryPage,
  mediaDiscoveryAvailabilityLabel
} from "./discovery";

function item(overrides: Record<string, unknown> = {}) {
  return {
    providerMediaId: "157336",
    mediaType: "movie" as const,
    title: " Interstellar ",
    year: 2014,
    overview: " Space. ",
    posterPath: "/poster.jpg",
    availability: "not_tracked" as const,
    requestEligible: true,
    ...overrides
  };
}

describe("Media discovery Portal contracts", () => {
  it("normalizes a read-only discovery item", () => {
    expect(createMediaDiscoveryItem(item())).toEqual({
      providerMediaId: "157336",
      mediaType: "movie",
      title: "Interstellar",
      year: 2014,
      overview: "Space.",
      posterPath: "/poster.jpg",
      availability: "not_tracked",
      requestEligible: true
    });
  });

  it("requires a positive numeric TMDB identity", () => {
    for (const providerMediaId of ["", "abc", "tmdb:1", "0", "-1"]) {
      expect(() =>
        createMediaDiscoveryItem(
          item({
            providerMediaId
          })
        )
      ).toThrow();
    }
  });

  it("accepts movie and tv only", () => {
    expect(() =>
      createMediaDiscoveryItem(
        item({
          mediaType: "anime_tv"
        })
      )
    ).toThrow("mediaType must be movie or tv.");
  });

  it("requires eligibility to exactly match provider tracking state", () => {
    expect(() =>
      createMediaDiscoveryItem(
        item({
          availability: "available",
          requestEligible: true
        })
      )
    ).toThrow("requestEligible does not match");

    expect(() =>
      createMediaDiscoveryItem(
        item({
          availability: "not_tracked",
          requestEligible: false
        })
      )
    ).toThrow("requestEligible does not match");
  });

  it("normalizes every supported tracked availability label", () => {
    expect(mediaDiscoveryAvailabilityLabel("unknown")).toBe("Unknown");
    expect(mediaDiscoveryAvailabilityLabel("pending")).toBe("Pending");
    expect(mediaDiscoveryAvailabilityLabel("processing")).toBe("Processing");
    expect(mediaDiscoveryAvailabilityLabel("partially_available")).toBe("Partially available");
    expect(mediaDiscoveryAvailabilityLabel("available")).toBe("Available");
    expect(mediaDiscoveryAvailabilityLabel("blocklisted")).toBe("Blocklisted");
    expect(mediaDiscoveryAvailabilityLabel("deleted")).toBe("Deleted");
  });

  it("derives provider pagination rather than trusting transport next-page state", () => {
    expect(
      createMediaDiscoveryPage({
        items: [item()],
        page: 2,
        totalPages: 4
      })
    ).toMatchObject({
      page: 2,
      totalPages: 4,
      nextPage: 3
    });
  });

  it("supports an empty zero-page discovery result", () => {
    expect(
      createMediaDiscoveryPage({
        items: [],
        page: 1,
        totalPages: 0
      })
    ).toEqual({
      items: [],
      page: 1,
      totalPages: 0,
      nextPage: null
    });
  });

  it("rejects duplicate media identity within one page", () => {
    expect(() =>
      createMediaDiscoveryPage({
        items: [item(), item()],
        page: 1,
        totalPages: 1
      })
    ).toThrow("Media discovery identities must be unique");
  });

  it("rejects non-relative poster metadata", () => {
    expect(() =>
      createMediaDiscoveryItem(
        item({
          posterPath: "https://example.com/poster.jpg"
        })
      )
    ).toThrow("posterPath must be a relative provider path.");
  });
});
