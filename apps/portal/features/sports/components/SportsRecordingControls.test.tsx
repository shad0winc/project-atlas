import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

describe("Sports explicit recording controls", () => {
  it("keeps recording separate from request and unfollow", () => {
    const source = readFileSync(new URL("./SportsRequestView.tsx", import.meta.url), "utf8");
    expect(source).toContain('"Record event"');
    expect(source).toContain('"Cancel recording"');
    expect(source).toContain("onSetRecording(event, !recording)");
    expect(source).toContain('"Request event"');
    expect(source).toContain('"Unfollow"');
  });
});
