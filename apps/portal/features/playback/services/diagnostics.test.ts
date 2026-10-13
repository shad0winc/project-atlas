import { describe, expect, it, vi } from "vitest";
import { createPlaybackDiagnostics } from "./diagnostics";
const video = { currentTime: 345.36, paused: false, readyState: 2, error: null,
  buffered: { length: 1, start: () => 151.62, end: () => 342.43 } };

describe("opt-in HLS diagnostics", () => {
  it("does not emit when disabled", () => {
    const write = vi.fn();
    createPlaybackDiagnostics(video, { enabled: () => false, write })("hls_error", { fatal: true });
    expect(write).not.toHaveBeenCalled();
  });
  it("records safe error metadata and the stalled buffer without URLs or tokens", () => {
    const write = vi.fn();
    createPlaybackDiagnostics(video, { enabled: () => true, now: () => 100000, write })("hls_error", {
      type: "mediaError", details: "bufferStalledError", fatal: false, responseStatus: 200,
      fragmentSequence: 170, url: "https://secret.example/private?token=secret", error: new Error("credential secret"),
      response: { headers: { authorization: "secret" } },
    });
    const output = write.mock.calls[0][0];
    expect(output).not.toContain("secret");
    const row = JSON.parse(output.slice("ATLAS_HLS ".length));
    expect(row).toMatchObject({ type: "mediaError", details: "bufferStalledError", fatal: false, responseStatus: 200, position: 345.36, buffered: [[151.62, 342.43]] });
  });
  it("rejects unexpected text and non-finite fields", () => {
    const write = vi.fn();
    createPlaybackDiagnostics(video, { enabled: () => true, write })("hls_error", {
      type: "https://private.example", details: "Bearer secret", fragmentStart: Infinity,
    });
    const output = write.mock.calls[0][0];
    expect(output).not.toContain("private.example");
    expect(output).not.toContain("Bearer");
    expect(JSON.parse(output.slice(10))).toMatchObject({ type: null, details: null, fragmentStart: null });
  });
  it("samples fragment progress and preserves intervening error events", () => {
    let time = 100000;
    const write = vi.fn();
    const record = createPlaybackDiagnostics(video, { enabled: () => true, now: () => time, write });
    record("fragment_loaded"); record("fragment_loaded"); record("hls_error");
    time += 10000; record("fragment_loaded");
    expect(write).toHaveBeenCalledTimes(3);
  });
  it("bounds output and contains storage and writer failures", () => {
    const write = vi.fn();
    const record = createPlaybackDiagnostics(video, { enabled: () => true, write });
    for (let index = 0; index < 250; index++) record("hls_error");
    expect(write).toHaveBeenCalledTimes(200);
    expect(() => createPlaybackDiagnostics(video, { enabled: () => { throw new Error("storage"); } })("hls_error")).not.toThrow();
    expect(() => createPlaybackDiagnostics(video, { enabled: () => true, write: () => { throw new Error("console"); } })("hls_error")).not.toThrow();
  });
});
