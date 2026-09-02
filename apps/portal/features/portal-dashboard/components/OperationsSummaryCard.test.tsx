import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { PortalOperationsSnapshot } from "../types/operations";

import { OperationsSummaryCard } from "./OperationsSummaryCard";

function operations(): PortalOperationsSnapshot {
  return {
    status: "available",
    detail: null,
    summary: {
      status: "healthy",
      score: 100,
      attentionCount: 0,
      generatedAt: "2026-08-24T00:31:57.503Z",
      currentness: "historical"
    },
    comparison: {
      status: "unavailable",
      scoreDelta: null,
      attentionDelta: null,
      addedCount: null,
      removedCount: null,
      changedCount: null,
      unchangedCount: null,
      differenceCount: null,
      detail: "At least two persisted Operations reports are required for comparison."
    },
    recentAttention: []
  };
}

describe("OperationsSummaryCard", () => {
  it("labels persisted Operations evidence as historical rather than current health", () => {
    const markup = renderToStaticMarkup(<OperationsSummaryCard operations={operations()} />);

    expect(markup).toContain("Historical snapshot");
    expect(markup).toContain("Report status:");
    expect(markup).toContain("healthy");
    expect(markup).toContain("Score: 100");
    expect(markup).toContain(
      "This is the latest persisted Operations snapshot and does not represent current system health."
    );
  });
});
