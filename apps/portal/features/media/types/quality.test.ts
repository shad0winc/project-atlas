import { expect, it } from "vitest";
import { sourceQuality } from "./quality";
it("discloses dimensions, letterboxed HD/4K and below-HD", () => {
  expect(sourceQuality(3840,1600)).toBe("4K · 3840×1600");
  expect(sourceQuality(1920,800)).toBe("HD · 1920×800");
  expect(sourceQuality(1280,720)).toBe("HD · 1280×720");
  expect(sourceQuality(720,480)).toBe("Below HD · 720×480");
});
it("does not invent quality for missing or invalid dimensions", () => {
  for (const pair of [[undefined,undefined],[1920,undefined],[NaN,720],[-1,720],[1920,0],[1.5,720],[100000,720]])
    expect(sourceQuality(...pair)).toBe("Quality unknown");
});
