import { describe, it, expect, vi } from "vitest";
import { listSavedResumes, readResume, resumeKey, restoreContinuity, writeResume } from "./continuity";
function storage() {
  const rows = new Map<string, string>();
  return { get length() { return rows.size; }, key: (index: number) => [...rows.keys()][index] ?? null, getItem: (k: string) => rows.get(k) ?? null, setItem: (k: string, v: string) => { rows.set(k,v); }, removeItem: (k: string) => { rows.delete(k); } };
}
function video() {
  return { currentTime: 0, duration: 500, readyState: 2, seekable: { length: 1, start: () => 0, end: () => 500 }, play: vi.fn(async () => {}) };
}
describe("playback continuity", () => {
  it("isolates viewers, providers and actual playable episodes", () => {
    const s = storage(); const key = resumeKey("a", "jellyfin", "episode1", true);
    writeResume(s,key,128); expect(readResume(s,key)).toBe(128);
    for (const other of [resumeKey("b","jellyfin","episode1",true),resumeKey("a","other","episode1",true),resumeKey("a","jellyfin","episode2",true)]) expect(readResume(s,other)).toBeNull();
    expect(resumeKey(undefined,"jellyfin","episode1",true)).toBeNull(); expect(resumeKey("a","jellyfin","live",false)).toBeNull();
  });
  it("lists only titled progress for this viewer and preserves old direct resume positions", () => {
    const s = storage();
    const old = resumeKey("a", "jellyfin", "legacy", true);
    const exact = resumeKey("a", "jellyfin", "episode2", true);
    writeResume(s, old, 60);
    writeResume(s, exact, 128, false, { title: "Episode two", duration: 300, episode: true });
    writeResume(s, resumeKey("b", "jellyfin", "episode1", true), 80, false, { title: "Private episode" });
    expect(readResume(s, old)).toBe(60);
    expect(listSavedResumes(s, "a")).toEqual([{
      provider: "jellyfin", itemId: "episode2", title: "Episode two", position: 128,
      duration: 300, episode: true, updatedAt: expect.any(Number)
    }]);
    writeResume(s, exact, 300, true);
    expect(listSavedResumes(s, "a")).toEqual([]);
  });
  it("survives reload and clears ended or explicitly restarted playback", () => {
    const s=storage(); writeResume(s,"k",128); expect(readResume(s,"k")).toBe(128);
    writeResume(s,"k",500,true); expect(readResume(s,"k")).toBeNull();
    writeResume(s,"k",128); writeResume(s,"k",0); expect(readResume(s,"k")).toBeNull();
  });
  it("ignores malformed records and storage failures", () => {
    const s=storage(); for (const value of ['oops','{"position":-1}','{"position":"128"}','{}']) {s.setItem("k",value); expect(readResume(s,"k")).toBeNull();}
    const denied={getItem:()=>{throw Error();},setItem:()=>{throw Error();},removeItem:()=>{throw Error();}};
    expect(readResume(denied,"k")).toBeNull(); expect(()=>writeResume(denied,"k",128)).not.toThrow();
  });
  it("waits for media readiness and a usable HLS seekable window", async () => {
    const v=video(); v.readyState=1; expect((await restoreContinuity(v,128,true)).restored).toBe(false);
    v.readyState=2; v.seekable.length=0; expect((await restoreContinuity(v,128,true)).restored).toBe(false);
    expect(v.play).not.toHaveBeenCalled(); v.seekable.length=1;
    expect(await restoreContinuity(v,128,true)).toEqual({restored:true,blocked:false}); expect(v.currentTime).toBe(128); expect(v.play).toHaveBeenCalledOnce();
  });
  it("preserves a deliberate pause while changing streams", async () => {
    const v=video(); await restoreContinuity(v,128,false); expect(v.currentTime).toBe(128); expect(v.play).not.toHaveBeenCalled();
  });
  it("attempts initial playback and reports an autoplay rejection", async () => {
    const v=video(); v.play.mockRejectedValue(new Error("NotAllowedError"));
    expect(await restoreContinuity(v,null,true)).toEqual({restored:true,blocked:true});
  });
  it("clamps stale positions to the media duration", async () => {
    const v=video(); await restoreContinuity(v,700,false); expect(v.currentTime).toBe(499);
  });
  it("retains the position when seeking is rejected", async () => {
    const v=video(); Object.defineProperty(v,"currentTime",{get:()=>0,set:()=>{throw Error();}});
    expect((await restoreContinuity(v,128,true)).restored).toBe(false); expect(v.play).not.toHaveBeenCalled();
  });
});
