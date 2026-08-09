import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { createMediaDiscoveryPage } from "../types/discovery";

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
      onPage={noop}
      onRefresh={noop}
      onRequestMovie={noop}
      onSearch={noop}
      requestActions={{}}
      state={state}
      {...overrides}
    />
  );
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

  it("defers TV mutation until season selection is explicit", () => {
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
        canCreateRequests: true
      }
    );

    expect(markup).toContain("Choose a season before requesting TV");

    expect(markup).not.toContain("Request movie");

    expect(markup).not.toContain("1396");
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
});
