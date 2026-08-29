import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { PortalOperationsSnapshot } from "../types/operations";

import { OperationsAttentionPanel } from "./OperationsAttentionPanel";

function operations(overrides: Partial<PortalOperationsSnapshot> = {}): PortalOperationsSnapshot {
  return {
    status: "available",
    detail: null,
    summary: {
      status: "warning",
      score: 82,
      attentionCount: 2,
      generatedAt: "2026-08-04T14:00:00.000Z",
      currentness: "historical"
    },
    comparison: {
      status: "available",
      scoreDelta: -3,
      attentionDelta: 2,
      addedCount: 1,
      removedCount: 0,
      changedCount: 1,
      unchangedCount: 4,
      differenceCount: 2,
      detail: null
    },
    recentAttention: [],
    ...overrides
  };
}

describe("OperationsAttentionPanel", () => {
  it("renders a clear state when there are no findings", () => {
    const markup = renderToStaticMarkup(<OperationsAttentionPanel operations={operations()} />);

    expect(markup).toContain("Recent attention");
    expect(markup).toContain("Clear");
    expect(markup).toContain("No findings required attention in this Operations snapshot.");
    expect(markup).not.toContain("current Operations findings");
  });

  it("renders findings, severity, messages, and recommendations", () => {
    const markup = renderToStaticMarkup(
      <OperationsAttentionPanel
        operations={operations({
          recentAttention: [
            {
              section: "services",
              identifier: "sonarr",
              name: "Sonarr",
              status: "warning",
              severity: "warning",
              message: "Sonarr connectivity is degraded.",
              recommendation: "Review Sonarr connectivity."
            },
            {
              section: "storage",
              identifier: "media",
              name: "Media storage",
              status: "critical",
              severity: "critical",
              message: "Media storage is unavailable.",
              recommendation: null
            }
          ]
        })}
      />
    );

    expect(markup).toContain("2 findings");
    expect(markup).toContain("Sonarr");
    expect(markup).toContain("Sonarr connectivity is degraded.");
    expect(markup).toContain("Recommendation: Review Sonarr connectivity.");
    expect(markup).toContain("warning");
    expect(markup).toContain("Media storage");
    expect(markup).toContain("critical");
  });

  it("renders the singular finding label", () => {
    const markup = renderToStaticMarkup(
      <OperationsAttentionPanel
        operations={operations({
          recentAttention: [
            {
              section: "scheduler",
              identifier: "operations.collect",
              name: "Operations collection",
              status: "warning",
              severity: "info",
              message: "Collection completed later than expected.",
              recommendation: null
            }
          ]
        })}
      />
    );

    expect(markup).toContain("1 finding");
    expect(markup).not.toContain("1 findings");
  });

  it("renders unavailable Operations detail without findings", () => {
    const markup = renderToStaticMarkup(
      <OperationsAttentionPanel
        operations={operations({
          status: "unavailable",
          detail: "Operations reports are unavailable.",
          summary: null,
          comparison: {
            status: "unavailable",
            scoreDelta: null,
            attentionDelta: null,
            addedCount: null,
            removedCount: null,
            changedCount: null,
            unchangedCount: null,
            differenceCount: null,
            detail: "Comparison is unavailable."
          },
          recentAttention: []
        })}
      />
    );

    expect(markup).toContain("Unavailable");
    expect(markup).toContain("Operations reports are unavailable.");
    expect(markup).not.toContain('class="status-list"');
  });
});
