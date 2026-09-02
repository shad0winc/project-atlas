import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

describe("Sports discovery UX contract", () => {
  const view = readFileSync(
    new URL("./SportsRequestView.tsx", import.meta.url),
    "utf8"
  );

  it("keeps browse failures on the originating card", () => {
    expect(view).toContain('error?.identity === `browse:${identity}`');
    expect(view).toContain(
      'error?.identity === `browse:${follow.subscriptionId}`'
    );
    expect(view).toContain("Could not load upcoming events");
  });

  it("clears the query after a new follow succeeds", () => {
    expect(view).toContain("await onFollow(result.kind, result.id);");
    expect(view).toContain('setQuery("");');
  });

  it("gives upcoming events a stable scroll destination", () => {
    expect(view).toContain('id="sports-upcoming-events"');
    expect(view).toContain('"Loading upcoming..."');
  });
});
