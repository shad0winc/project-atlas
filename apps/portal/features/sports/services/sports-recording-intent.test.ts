import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

describe("Sports recording intent transport", () => {
  it("uses the explicit recording PATCH endpoint", () => {
    const source = readFileSync(new URL("./sports.ts", import.meta.url), "utf8");
    expect(source).toContain("updateSportsRecordingIntent");
    expect(source).toContain("/recording`");
    expect(source).toContain('method: "PATCH"');
    expect(source).toContain("body: { record }");
  });
});
