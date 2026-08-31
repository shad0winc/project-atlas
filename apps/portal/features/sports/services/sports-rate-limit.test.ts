import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Sports search rate-limit contract", () => {
  const source = readFileSync(
    new URL("./sports.ts", import.meta.url),
    "utf8"
  );

  it("uses the established Atlas API rate-limit classification", () => {
    expect(source).toContain("error instanceof AtlasApiError");
    expect(source).toContain('error.kind === "rate-limit"');
  });

  it("does not automatically retry Sports searches", () => {
    expect(source).toContain("maxRetries: 0");
  });

  it("shows a Sports-specific temporary rate-limit message", () => {
    expect(source).toContain(
      "Sports search is temporarily rate limited."
    );
  });
});
