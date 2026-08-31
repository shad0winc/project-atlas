import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

describe("Sports page UX coordination", () => {
  const source = readFileSync(
    new URL("../../../app/(protected)/portal/sports/SportsPageClient.tsx", import.meta.url),
    "utf8"
  );

  it("removes a successfully followed result from Discover", () => {
    expect(source).toContain(
      "current.filter((item) => item.id !== providerId)"
    );
  });

  it("scrolls to Upcoming Events after browse succeeds", () => {
    expect(source).toContain(
      'getElementById("sports-upcoming-events")'
    );
    expect(source).toContain(
      'scrollIntoView({ behavior: "smooth", block: "start" })'
    );
  });
});
