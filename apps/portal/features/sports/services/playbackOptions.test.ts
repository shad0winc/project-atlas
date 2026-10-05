import { describe, expect, it } from "vitest";
import { parseSportsPlaybackOptions, preferredSportsPlaybackOption } from "./playbackOptions";

describe("playback choices", () => {
  const primary = { option_id: "primary", label: "Primary", configured: true };
  it("accepts legacy empty choices and at most three explicit choices", () => {
    expect(parseSportsPlaybackOptions({ options: [] })).toEqual([]);
    expect(parseSportsPlaybackOptions({ options: [primary, { option_id: "backup-1", label: "Backup 1", configured: false }] })).toEqual([
      { optionId: "primary", label: "Primary", configured: true }, { optionId: "backup-1", label: "Backup 1", configured: false },
    ]);
  });
  it.each([
    { options: [primary, primary] }, { options: [{ ...primary, stream_url: "private" }] },
    { options: [{ ...primary, configured: "yes" }] }, { options: [primary, primary, primary, primary] },
    { options: [{ ...primary, option_id: "foreign" }] },
  ])("rejects malformed or private route payloads", payload => {
    expect(() => parseSportsPlaybackOptions(payload)).toThrow();
  });
});

it("starts Primary automatically with three choices and retains the legacy default", () => {
  expect(preferredSportsPlaybackOption([])).toBeUndefined();
  expect(preferredSportsPlaybackOption([
    { optionId: "primary", label: "Primary", configured: true },
    { optionId: "backup-1", label: "Backup 1", configured: true },
    { optionId: "backup-2", label: "Backup 2", configured: true },
  ])).toBe("primary");
});
it("does not silently select a backup when Primary is unpublished", () => {
  expect(() => preferredSportsPlaybackOption([
    { optionId: "primary", label: "Primary", configured: false },
    { optionId: "backup-1", label: "Backup 1", configured: true },
  ])).toThrow("Primary playback setup is pending");
});
