import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { PortalOperationsComparison } from "../types/operations";

import { OperationsComparisonCard } from "./OperationsComparisonCard";

function comparison(
  overrides: Partial<PortalOperationsComparison> = {}
): PortalOperationsComparison {
  return {
    status: "available",
    scoreDelta: 3,
    attentionDelta: -2,
    addedCount: 1,
    removedCount: 2,
    changedCount: 3,
    unchangedCount: 4,
    differenceCount: 6,
    detail: null,
    ...overrides
  };
}

describe("OperationsComparisonCard", () => {
  it("renders available comparison metrics and signed deltas", () => {
    const markup = renderToStaticMarkup(<OperationsComparisonCard comparison={comparison()} />);

    expect(markup).toContain("Operations comparison");
    expect(markup).toContain("Available");
    expect(markup).toContain("Score change: +3");
    expect(markup).toContain("Attention change: -2");
    expect(markup).toContain("Added: 1");
    expect(markup).toContain("Removed: 2");
    expect(markup).toContain("Changed: 3");
    expect(markup).toContain("Unchanged: 4");
    expect(markup).toContain("Total differences: 6");
  });

  it("renders zero deltas without a positive sign", () => {
    const markup = renderToStaticMarkup(
      <OperationsComparisonCard
        comparison={comparison({
          scoreDelta: 0,
          attentionDelta: 0
        })}
      />
    );

    expect(markup).toContain("Score change: 0");
    expect(markup).toContain("Attention change: 0");
    expect(markup).not.toContain("Score change: +0");
  });

  it("renders unavailable comparison detail", () => {
    const markup = renderToStaticMarkup(
      <OperationsComparisonCard
        comparison={comparison({
          status: "unavailable",
          scoreDelta: null,
          attentionDelta: null,
          addedCount: null,
          removedCount: null,
          changedCount: null,
          unchangedCount: null,
          differenceCount: null,
          detail: "Two reports are required."
        })}
      />
    );

    expect(markup).toContain("Unavailable");
    expect(markup).toContain("Two reports are required.");
    expect(markup).not.toContain("Score change:");
  });
});
