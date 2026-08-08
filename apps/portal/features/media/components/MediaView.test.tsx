import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { createMediaSnapshot } from "../types/media";

import { MediaError } from "./MediaError";
import { MediaLibraryGrid } from "./MediaLibraryGrid";
import { MediaOverview } from "./MediaOverview";
import { MediaSkeleton } from "./MediaSkeleton";

describe("Media presentation", () => {
  it("renders accessible loading content", () => {
    const markup = renderToStaticMarkup(<MediaSkeleton />);

    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain('aria-label="Loading media libraries"');
  });

  it("renders an actionable request error", () => {
    const markup = renderToStaticMarkup(
      <MediaError message="Media request failed." onRetry={() => undefined} />
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Media request failed.");
    expect(markup).toContain("Try again");
  });

  it("renders a successful empty result distinctly from an error", () => {
    const markup = renderToStaticMarkup(<MediaLibraryGrid libraries={[]} />);

    expect(markup).toContain("No media libraries were returned");
    expect(markup).not.toContain('role="alert"');
  });

  it("renders aggregate totals and unavailable libraries", () => {
    const snapshot = createMediaSnapshot({
      generatedAt: "2026-07-27T22:00:00Z",
      libraries: [
        {
          id: "movies",
          label: "Movies",
          status: "available",
          count: 14
        },
        {
          id: "tv",
          label: "Television",
          status: "available",
          count: 6
        },
        {
          id: "photos",
          label: "Photos",
          status: "unavailable",
          detail: "Provider unavailable"
        }
      ]
    });

    const markup = renderToStaticMarkup(<MediaOverview snapshot={snapshot} />);

    expect(markup).toContain("Configured libraries");
    expect(markup).toContain("Represented items");
    expect(markup).toContain("Movies");
    expect(markup).toContain("14");
    expect(markup).toContain("Photos");
    expect(markup).toContain("Unavailable");
    expect(markup).toContain("Provider unavailable");
  });
});
