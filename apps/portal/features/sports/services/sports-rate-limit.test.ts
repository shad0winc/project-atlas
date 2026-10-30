import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { SportsDiscoveryRateLimitError } from "./federatedDiscovery";

describe("Sports search rate-limit contract", () => {
  const source = readFileSync(
    new URL("./sports.ts", import.meta.url),
    "utf8"
  );

  it("uses the established Atlas API rate-limit classification", () => {
    expect(source).toContain("error instanceof AtlasApiError");
    expect(source).toContain('error.kind === "rate-limit"');
  });

  it("keeps transport retries disabled while pacing safe Sports reads", () => {
    expect(source).toContain("maxRetries: 0");
    expect(source).toContain("withSportsBudgetRetry(");
  });

  it("shows a Sports-specific temporary rate-limit message", () => {
    expect(new SportsDiscoveryRateLimitError().message).toContain(
      "Sports search is temporarily rate limited."
    );
  });
});
