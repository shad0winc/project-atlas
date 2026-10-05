import { describe, expect, it } from "vitest";
import { safeLiveSeekPosition } from "./live-seek";

function ranges(values: number[][]): TimeRanges {
  return { length: values.length, start: i => values[i][0], end: i => values[i][1] };
}
function video(buffered: number[][], seekable: number[][]) {
  return { buffered: ranges(buffered), seekable: ranges(seekable) };
}

describe("live user seek safety", () => {
  const observed = video([[0.066733, 30.047249]], [[0, 30.096733333333333]]);
  it("protects the observed unavailable zero position", () => {
    expect(safeLiveSeekPosition(observed, 0)).toBe(7);
  });
  it("keeps seven seconds of buffered media ahead at the live edge", () => {
    expect(safeLiveSeekPosition(observed, 30.096733333333333)).toBeCloseTo(23.047249);
  });
  it("preserves a valid requested position", () => {
    expect(safeLiveSeekPosition(observed, 22.31176)).toBe(22.31176);
  });
  it("uses the moving window rather than a permanent seven-second floor", () => {
    const moving = video([[100.2, 130]], [[100, 135]]);
    expect(safeLiveSeekPosition(moving, 7)).toBeCloseTo(100.45);
    expect(safeLiveSeekPosition(moving, 135)).toBe(123);
  });
  it("does not put a seek in an unbuffered gap", () => {
    expect(safeLiveSeekPosition(video([[0, 30], [40, 70]], [[0, 70]]), 35)).toBe(40.25);
  });
  it("honors a narrower seekable window", () => {
    expect(safeLiveSeekPosition(video([[0, 100]], [[50, 80]]), 100)).toBe(73);
  });
  it("declines a seek when the startup buffer is too short", () => {
    expect(safeLiveSeekPosition(video([[0, 10]], [[0, 10]]), 0)).toBeNull();
  });
  it("declines empty windows and invalid positions", () => {
    expect(safeLiveSeekPosition(video([], []), 0)).toBeNull();
    expect(safeLiveSeekPosition(observed, NaN)).toBeNull();
  });
});
