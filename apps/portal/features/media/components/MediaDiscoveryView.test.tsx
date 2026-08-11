import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { createMediaDiscoveryPage } from "../types/discovery";
import { createMediaSeriesDetail } from "../types/series";

import { MediaDiscoveryContent } from "./MediaDiscoveryView";

const noop = (): void => undefined;

function render(
  state: Parameters<typeof MediaDiscoveryContent>[0]["state"],
  overrides: Partial<Parameters<typeof MediaDiscoveryContent>[0]> = {}
): string {
  return renderToStaticMarkup(
    <MediaDiscoveryContent
      activeQuery=""
      canCreateRequests={false}
      mediaType="movie"
      mode="discover"
      onBrowse={noop}
      onLoadTvSeasons={noop}
      onPage={noop}
      onRefresh={noop}
      onRequestMovie={noop}
      onRequestTvSeason={noop}
      onSearch={noop}
      requestActions={{}}
      seriesStates={{}}
      state={state}
      {...overrides}
    />
  );
}

function tvDetail() {
  return createMediaSeriesDetail({
    providerMediaId: "1396",
    title: "Breaking Bad",
    year: 2008,
    status: "ended",
    inProduction: false,
    isOngoing: false,
    isAnime: false,
    availability: "partially_available",
    requestEligible: false,
    seasons: [
      {
        seasonNumber: 1,
        name: "Season 1",
        episodeCount: 7,
        availability: "available",
        requestabilityKnown: true,
        requestEligible: false
      },
      {
        seasonNumber: 2,
        name: "Season 2",
        episodeCount: 13,
        availability: "unknown",
        requestabilityKnown: true,
        requestEligible: true
      },
      {
        seasonNumber: 3,
        name: "Season 3",
        episodeCount: 13,
        availability: "unknown",
        requestabilityKnown: false,
        requestEligible: false
      }
    ]
  });
}

describe("Media discovery presentation", () => {
  it("renders accessible loading content", () => {
    const markup = render({
      status: "loading"
    });

    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain('aria-label="Loading media discovery results"');
  });

  it("keeps search available while discovery is loading", () => {
    const markup = render(
      {
        status: "loading"
      },
      {
        activeQuery: "Star Wars"
      }
    );

    expect(markup).toContain('value="Star Wars"');
    expect(markup).not.toMatch(/class="media-discovery-primary-button"[^>]*disabled/);
  });

  it("renders provider errors distinctly from empty results", () => {
    const markup = render({
      status: "error",
      error: new Error("Media discovery is unavailable.")
    });

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Media discovery is unavailable.");
    expect(markup).toContain("Try again");
  });

  it("renders an empty successful search result", () => {
    const markup = render(
      {
        status: "ready",
        data: createMediaDiscoveryPage({
          items: [],
          page: 1,
          totalPages: 0
        })
      },
      {
        mode: "search",
        activeQuery: "No Such Movie"
      }
    );

    expect(markup).toContain("Search results");
    expect(markup).toContain("No media results");
    expect(markup).not.toContain('role="alert"');
  });

  it("renders movie and TV identity without exposing raw provider IDs", () => {
    const markup = render({
      status: "ready",
      data: createMediaDiscoveryPage({
        items: [
          {
            providerMediaId: "157336",
            mediaType: "movie",
            title: "Interstellar",
            year: 2014,
            overview: "Space.",
            availability: "not_tracked",
            requestEligible: true
          },
          {
            providerMediaId: "1396",
            mediaType: "tv",
            title: "Breaking Bad",
            year: 2008,
            availability: "available",
            requestEligible: false
          }
        ],
        page: 1,
        totalPages: 1
      })
    });

    expect(markup).toContain("Interstellar");
    expect(markup).toContain("Breaking Bad");
    expect(markup).toContain("Not tracked");
    expect(markup).toContain("Available");

    expect(markup).not.toContain("157336");
    expect(markup).not.toContain("1396");
  });

  it("renders search context and page status", () => {
    const markup = render(
      {
        status: "ready",
        data: createMediaDiscoveryPage({
          items: [],
          page: 2,
          totalPages: 3
        })
      },
      {
        mode: "search",
        activeQuery: "Star Wars"
      }
    );

    expect(markup).toContain("Search results for");
    expect(markup).toContain("Star Wars");
    expect(markup).toContain("Page 2 of 3");
  });

  it("offers eligible movie requests only with requests.create presentation permission", () => {
    const state = {
      status: "ready" as const,
      data: createMediaDiscoveryPage({
        items: [
          {
            providerMediaId: "157336",
            mediaType: "movie",
            title: "Interstellar",
            availability: "not_tracked",
            requestEligible: true
          }
        ],
        page: 1,
        totalPages: 1
      })
    };

    expect(render(state)).not.toContain("Request movie");

    const permitted = render(state, {
      canCreateRequests: true
    });

    expect(permitted).toContain("Request movie");

    expect(permitted).not.toContain("157336");
  });

  it("allows tracked TV titles to open explicit season availability", () => {
    const markup = render(
      {
        status: "ready",
        data: createMediaDiscoveryPage({
          items: [
            {
              providerMediaId: "1396",
              mediaType: "tv",
              title: "Breaking Bad",
              availability: "partially_available",
              requestEligible: false
            }
          ],
          page: 1,
          totalPages: 1
        })
      },
      {
        canCreateRequests: true
      }
    );

    expect(markup).toContain("View seasons");
    expect(markup).not.toContain("Request Season");
    expect(markup).not.toContain("Request movie");
    expect(markup).not.toContain("1396");
  });

  it("renders only truthful explicit season request actions", () => {
    const detail = tvDetail();

    const markup = render(
      {
        status: "ready",
        data: createMediaDiscoveryPage({
          items: [
            {
              providerMediaId: "1396",
              mediaType: "tv",
              title: "Breaking Bad",
              availability: "partially_available",
              requestEligible: false
            }
          ],
          page: 1,
          totalPages: 1
        })
      },
      {
        canCreateRequests: true,
        seriesStates: {
          "tv:1396": {
            status: "ready",
            detail
          }
        }
      }
    );

    expect(markup).toContain("This season is already available.");
    expect(markup).toContain("Request Season 2");
    expect(markup).toContain("Request availability is currently unavailable for this season.");
    expect(markup).toContain("Season selection controls this Atlas request only.");
    expect(markup).not.toContain("Request Season 1");
    expect(markup).not.toContain("Request Season 3");
    expect(markup).not.toContain("All seasons");
    expect(markup).not.toContain("1396");
  });

  it("renders server-provided anime classification without title inference", () => {
    const detail = createMediaSeriesDetail({
      ...tvDetail(),
      isAnime: true
    });

    const markup = render(
      {
        status: "ready",
        data: createMediaDiscoveryPage({
          items: [
            {
              providerMediaId: "1396",
              mediaType: "tv",
              title: "Example Series",
              availability: "partially_available",
              requestEligible: false
            }
          ],
          page: 1,
          totalPages: 1
        })
      },
      {
        canCreateRequests: true,
        seriesStates: {
          "tv:1396": {
            status: "ready",
            detail
          }
        }
      }
    );

    expect(markup).toContain("Anime series");
    expect(markup).not.toContain("1396");
  });

  it("renders TV detail failure as retry-only state", () => {
    const markup = render(
      {
        status: "ready",
        data: createMediaDiscoveryPage({
          items: [
            {
              providerMediaId: "1396",
              mediaType: "tv",
              title: "Breaking Bad",
              availability: "not_tracked",
              requestEligible: true
            }
          ],
          page: 1,
          totalPages: 1
        })
      },
      {
        canCreateRequests: true,
        seriesStates: {
          "tv:1396": {
            status: "error",
            message: "Season availability is unavailable. Try again before requesting this title."
          }
        }
      }
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Retry seasons");
    expect(markup).not.toContain("Request Season");
  });

  it("renders per-card submitting and stale-conflict states without raw provider identity", () => {
    const state = {
      status: "ready" as const,
      data: createMediaDiscoveryPage({
        items: [
          {
            providerMediaId: "157336",
            mediaType: "movie",
            title: "Interstellar",
            availability: "not_tracked",
            requestEligible: true
          }
        ],
        page: 1,
        totalPages: 1
      })
    };

    const submitting = render(state, {
      canCreateRequests: true,
      requestActions: {
        "movie:157336": {
          status: "submitting",
          message: "Submitting Interstellar to Atlas…"
        }
      }
    });

    expect(submitting).toContain("Requesting…");

    expect(submitting).toContain('aria-busy="true"');

    expect(submitting).not.toContain("157336");

    const conflict = render(state, {
      canCreateRequests: true,
      requestActions: {
        "movie:157336": {
          status: "conflict",
          message: "This title already has an active Atlas request."
        }
      }
    });

    expect(conflict).toContain("Already requested");

    expect(conflict).toContain("This title already has an active Atlas request.");

    expect(conflict).not.toContain("157336");
  });
  it("renders per-season submitting and conflict states without raw provider identity", () => {
    const detail = tvDetail();
    const state = {
      status: "ready" as const,
      data: createMediaDiscoveryPage({
        items: [
          {
            providerMediaId: "1396",
            mediaType: "tv",
            title: "Breaking Bad",
            availability: "partially_available",
            requestEligible: false
          }
        ],
        page: 1,
        totalPages: 1
      })
    };

    const submitting = render(state, {
      canCreateRequests: true,
      seriesStates: {
        "tv:1396": {
          status: "ready",
          detail
        }
      },
      requestActions: {
        "tv:1396:season:2": {
          status: "submitting",
          message: "Submitting Breaking Bad Season 2 to Atlas…"
        }
      }
    });

    expect(submitting).toContain("Requesting…");
    expect(submitting).toContain('aria-busy="true"');
    expect(submitting).not.toContain("1396");

    const conflict = render(state, {
      canCreateRequests: true,
      seriesStates: {
        "tv:1396": {
          status: "ready",
          detail
        }
      },
      requestActions: {
        "tv:1396:season:2": {
          status: "conflict",
          message: "This title already has an active Atlas request."
        }
      }
    });

    expect(conflict).toContain("Already requested");
    expect(conflict).toContain("This title already has an active Atlas request.");
    expect(conflict).not.toContain("1396");
  });

});
