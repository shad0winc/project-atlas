import { describe, expect, it } from "vitest";

import { createMediaLibrary, createMediaSnapshot, summarizeMediaSnapshot } from "./media";

describe("Media domain model", () => {
  it("normalizes stable library identity and optional text", () => {
    expect(
      createMediaLibrary({
        id: " Movies ",
        label: " Movies ",
        status: "available",
        count: 12,
        detail: " Primary library "
      })
    ).toEqual({
      id: "movies",
      label: "Movies",
      status: "available",
      count: 12,
      detail: "Primary library"
    });
  });

  it("normalizes timestamps and child library contracts", () => {
    expect(
      createMediaSnapshot({
        generatedAt: "2026-07-27T22:00:00-04:00",
        libraries: [
          {
            id: " TV ",
            label: "Television",
            status: "available",
            count: 7
          }
        ]
      })
    ).toEqual({
      generatedAt: "2026-07-28T02:00:00.000Z",
      libraries: [
        {
          id: "tv",
          label: "Television",
          status: "available",
          count: 7
        }
      ]
    });
  });

  it("rejects duplicate normalized library identities", () => {
    expect(() =>
      createMediaSnapshot({
        generatedAt: "2026-07-27T22:00:00Z",
        libraries: [
          {
            id: "Movies",
            label: "Movies",
            status: "available",
            count: 1
          },
          {
            id: " movies ",
            label: "Movie archive",
            status: "available",
            count: 2
          }
        ]
      })
    ).toThrow("Media library IDs must be unique.");
  });

  it("requires counts for available libraries", () => {
    expect(() =>
      createMediaLibrary({
        id: "movies",
        label: "Movies",
        status: "available"
      })
    ).toThrow("Available media libraries require a nonnegative integer item count.");
  });

  it("rejects counts for unavailable libraries", () => {
    expect(() =>
      createMediaLibrary({
        id: "movies",
        label: "Movies",
        status: "unavailable",
        count: 0
      })
    ).toThrow("Unavailable media libraries cannot have an item count.");
  });

  it("summarizes available, unavailable, and total item counts", () => {
    const snapshot = createMediaSnapshot({
      generatedAt: "2026-07-27T22:00:00Z",
      libraries: [
        {
          id: "movies",
          label: "Movies",
          status: "available",
          count: 12
        },
        {
          id: "tv",
          label: "Television",
          status: "available",
          count: 8
        },
        {
          id: "photos",
          label: "Photos",
          status: "unavailable",
          detail: "Provider unavailable"
        }
      ]
    });

    expect(summarizeMediaSnapshot(snapshot)).toEqual({
      libraryCount: 3,
      availableLibraryCount: 2,
      unavailableLibraryCount: 1,
      totalItemCount: 20
    });
  });
});
