import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { DownloadsState } from "../types/downloads";
import { DownloadsContent } from "./DownloadsView";

function renderState(state: DownloadsState): string {
  return renderToStaticMarkup(<DownloadsContent refresh={() => undefined} state={state} />);
}

describe("Downloads presentation", () => {
  it("renders the bounded read-only download snapshot", () => {
    const markup = renderState({
      status: "ready",
      data: {
        schemaVersion: 1,
        generatedAt: "2026-08-30T00:30:00Z",
        summary: {
          active: 1,
          queued: 0,
          completed: 2,
          error: 0,
          downloadRate: 1048576,
          uploadRate: 524288
        },
        downloads: [
          {
            name: "Example Movie",
            category: "movies",
            state: "downloading",
            progress: 0.5,
            totalBytes: 2147483648,
            downloadedBytes: 1073741824,
            downloadRate: 1048576,
            uploadRate: 0,
            etaSeconds: 600
          },
          {
            name: "Example Complete",
            category: null,
            state: "seeding",
            progress: 1,
            totalBytes: 1024,
            downloadedBytes: 1024,
            downloadRate: 0,
            uploadRate: 1024,
            etaSeconds: null
          }
        ]
      }
    });

    expect(markup).toContain("Example Movie");
    expect(markup).toContain("Downloading");
    expect(markup).toContain("Seeding");
    expect(markup).toContain("Progress 50%");
    expect(markup).toContain(">Refresh</button>");
    expect(markup).not.toMatch(/hash|magnet|tracker|peer|save path/i);
  });

  it("renders an explicit valid empty state", () => {
    const markup = renderState({
      status: "ready",
      data: {
        schemaVersion: 1,
        generatedAt: "2026-08-30T00:30:00Z",
        summary: { active: 0, queued: 0, completed: 0, error: 0, downloadRate: 0, uploadRate: 0 },
        downloads: []
      }
    });

    expect(markup).toContain("No download activity");
  });

  it("renders unavailable state separately from an empty snapshot", () => {
    const markup = renderState({
      status: "error",
      error: new Error("Downloads runtime data is unavailable.")
    });

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Downloads unavailable");
    expect(markup).toContain(">Try again</button>");
  });

  it("renders an accessible loading state", () => {
    const markup = renderState({ status: "loading" });
    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain('aria-label="Loading download activity"');
  });
});
