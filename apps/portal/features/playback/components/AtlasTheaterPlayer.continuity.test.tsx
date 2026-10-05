// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { AtlasTheaterPlayer } from "./AtlasTheaterPlayer";
import type { PlaybackSession } from "../types/session";
vi.mock("../services/stream", () => ({ bootstrapPlaybackStream: async () => ({ streamUrl: "https://playback.example.test/videos/fixture/master.m3u8" }) }));
const session: PlaybackSession = {available:true,action:"watch_now",label:"Watch Now",backend:"jellyfin",sourceType:"library",provider:"jellyfin",requestedTargetId:"e1",playableTargetId:"e1",title:"Fixture",mediaType:"tv",canSeek:true,playbackBootstrapUrl:"",playbackCapability:"fixture",audioTracks:[],subtitleTracks:[{index:3,kind:"subtitle",label:"Signs & Songs",default:false,forced:false}],seriesId:"s1",nextTargetId:"e3"};
const hlsMock = vi.hoisted(() => ({
  supported: false,
  constructed: vi.fn(),
  attach: vi.fn(),
  source: vi.fn(),
  destroy: vi.fn()
}));
vi.mock("hls.js", () => ({ default: class {
  static isSupported() { return hlsMock.supported; }
  static Events = { ERROR: "error" };
  constructor(options: unknown) { hlsMock.constructed(options); }
  on() {}
  attachMedia(video: HTMLVideoElement) { hlsMock.attach(video); video.load(); }
  loadSource(source: string) { hlsMock.source(source); }
  destroy() { hlsMock.destroy(); }
} }));
let root: Root;
let container: HTMLDivElement;
let playing: boolean;
let blocked: boolean;
let play: Mock<() => Promise<void>>;
async function flush() { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); }
beforeEach(() => {
  Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
  playing=false; blocked=false; hlsMock.supported=false;
  hlsMock.constructed.mockClear(); hlsMock.attach.mockClear(); hlsMock.source.mockClear(); hlsMock.destroy.mockClear();
  window.localStorage.clear();
  vi.spyOn(HTMLMediaElement.prototype,"canPlayType").mockReturnValue("probably");
  vi.spyOn(HTMLMediaElement.prototype,"load").mockImplementation(function(this: HTMLMediaElement) {
    playing=false;
    Object.defineProperties(this,{readyState:{configurable:true,value:2},duration:{configurable:true,value:500},seekable:{configurable:true,value:{length:1,start:()=>0,end:()=>500}},paused:{configurable:true,get:()=>!playing}});
    queueMicrotask(()=>this.dispatchEvent(new Event("canplay")));
  });
  play=vi.fn(async function(this: HTMLMediaElement) {
    if(blocked) throw new Error("NotAllowedError");
    playing=true; this.dispatchEvent(new Event("play"));
  });
  vi.spyOn(HTMLMediaElement.prototype,"play").mockImplementation(play);
  vi.spyOn(HTMLMediaElement.prototype,"pause").mockImplementation(function(this:HTMLMediaElement){playing=false;this.dispatchEvent(new Event("pause"));});
  container=document.createElement("div");document.body.append(container);root=createRoot(container);
});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();vi.restoreAllMocks();});
describe("mounted player continuity",()=>{
  it("prefers managed HLS for library playback even when native HLS is supported", async () => {
    hlsMock.supported=true;
    await act(async()=>root.render(<AtlasTheaterPlayer session={session}/>));await flush();
    const video=container.querySelector("video")!;
    expect(hlsMock.attach).toHaveBeenCalledWith(video);
    expect(hlsMock.source).toHaveBeenCalledWith("https://playback.example.test/videos/fixture/master.m3u8");
    expect(video.getAttribute("src")).toBeNull();
    expect(playing).toBe(true);
    const options=hlsMock.constructed.mock.calls[0][0];
    const xhr={withCredentials:false}; options.xhrSetup(xhr);
    expect(xhr.withCredentials).toBe(true);
    await act(async()=>root.render(null));await flush();
    expect(hlsMock.destroy).toHaveBeenCalledTimes(1);
  });
  it("retains native HLS fallback when managed HLS is unsupported", async () => {
    await act(async()=>root.render(<AtlasTheaterPlayer session={session}/>));await flush();
    expect(container.querySelector("video")!.src).toContain("master.m3u8");
    expect(hlsMock.constructed).not.toHaveBeenCalled();
  });
  it.each(["maybe", "probably", ""] as const)("uses managed live HLS when native support is %s", async (nativeSupport) => {
    hlsMock.supported=true;
    vi.mocked(HTMLMediaElement.prototype.canPlayType).mockReturnValue(nativeSupport);
    await act(async()=>root.render(<AtlasTheaterPlayer session={{...session,sourceType:"live",canSeek:false}}/>));await flush();
    const video=container.querySelector("video")!;
    expect(hlsMock.attach).toHaveBeenCalledWith(video);
    expect(hlsMock.source).toHaveBeenCalledWith("https://playback.example.test/videos/fixture/master.m3u8");
    expect(video.getAttribute("src")).toBeNull();
    const options=hlsMock.constructed.mock.calls[0][0];
    const xhr={withCredentials:false}; options.xhrSetup(xhr);
    expect(xhr.withCredentials).toBe(true);
    expect(playing).toBe(true);
    await act(async()=>root.render(null));await flush();
    expect(hlsMock.destroy).toHaveBeenCalledTimes(1);
  });
  it("retains native live HLS when managed HLS is unavailable", async () => {
    hlsMock.supported=false;
    await act(async()=>root.render(<AtlasTheaterPlayer session={{...session,sourceType:"live",canSeek:false}}/>));await flush();
    expect(container.querySelector("video")!.src).toContain("master.m3u8");
    expect(hlsMock.constructed).not.toHaveBeenCalled();
    expect(playing).toBe(true);
  });
  it("starts live playback only once the media is ready", async () => {
    hlsMock.supported=true;
    vi.mocked(HTMLMediaElement.prototype.load).mockImplementation(function(this: HTMLMediaElement) {
      playing=false;
      Object.defineProperties(this, {readyState:{configurable:true,value:0},paused:{configurable:true,get:()=>!playing}});
    });
    await act(async()=>root.render(<AtlasTheaterPlayer session={{...session,sourceType:"live",canSeek:false}}/>));await flush();
    expect(play).not.toHaveBeenCalled();
    const video=container.querySelector("video")!;
    Object.defineProperty(video,"readyState",{configurable:true,value:2});
    await act(async()=>video.dispatchEvent(new Event("canplay")));await flush();
    expect(playing).toBe(true);
    await act(async()=>video.dispatchEvent(new Event("progress")));await flush();
    expect(play).toHaveBeenCalledTimes(1);
  });
  it("keeps the Play fallback when a browser blocks live startup", async () => {
    hlsMock.supported=true;blocked=true;
    await act(async()=>root.render(<AtlasTheaterPlayer session={{...session,sourceType:"live",canSeek:false}}/>));await flush();
    expect(playing).toBe(false);
    const button=Array.from(container.querySelectorAll("button")).find(x=>x.textContent==="Play")!;
    expect(button).toBeDefined();
    blocked=false;await act(async()=>button.click());await flush();
    expect(playing).toBe(true);
  });
  it("preserves a user pause when replacing live captions", async () => {
    hlsMock.supported=true;
    const live={...session,sourceType:"live" as const,canSeek:false};
    await act(async()=>root.render(<AtlasTheaterPlayer session={live} sessionResolver={async()=>({...live})}/>));await flush();
    const video=container.querySelector("video")!;
    await act(async()=>video.pause());
    const previousCalls=play.mock.calls.length;
    await act(async()=>{const select=container.querySelector("select")!;select.value="off";select.dispatchEvent(new Event("change",{bubbles:true}));});await flush();
    expect(playing).toBe(false);
    expect(play).toHaveBeenCalledTimes(previousCalls);
  });
  it("clamps live scrubbing at both edges without resuming a paused player", async () => {
    hlsMock.supported=true;
    await act(async()=>root.render(<AtlasTheaterPlayer session={{...session,sourceType:"live",canSeek:false}}/>));await flush();
    const video=container.querySelector("video")!;
    Object.defineProperties(video, {
      buffered:{configurable:true,value:{length:1,start:()=>0.066733,end:()=>30.047249}},
      seekable:{configurable:true,value:{length:1,start:()=>0,end:()=>30.096733333333333}}
    });
    await act(async()=>video.pause());
    const previousCalls=play.mock.calls.length;
    await act(async()=>{video.currentTime=0;video.dispatchEvent(new Event("seeking"));});
    expect(video.currentTime).toBe(7);
    await act(async()=>{video.currentTime=30.096733333333333;video.dispatchEvent(new Event("seeking"));});
    expect(video.currentTime).toBeCloseTo(23.047249);
    expect(playing).toBe(false);expect(play).toHaveBeenCalledTimes(previousCalls);
    Object.defineProperties(video, {
      buffered:{configurable:true,value:{length:1,start:()=>100.2,end:()=>130}},
      seekable:{configurable:true,value:{length:1,start:()=>100,end:()=>135}}
    });
    await act(async()=>{video.currentTime=7;video.dispatchEvent(new Event("seeking"));});
    expect(video.currentTime).toBeCloseTo(100.45);
    await act(async()=>root.render(null));await flush();
    video.currentTime=0;video.dispatchEvent(new Event("seeking"));
    expect(video.currentTime).toBe(0);
  });
  it("leaves library scrubbing unchanged", async () => {
    await act(async()=>root.render(<AtlasTheaterPlayer session={session}/>));await flush();
    const video=container.querySelector("video")!;
    Object.defineProperty(video,"buffered",{configurable:true,value:{length:1,start:()=>0,end:()=>30}});
    await act(async()=>{video.currentTime=0;video.dispatchEvent(new Event("seeking"));});
    expect(video.currentTime).toBe(0);
    await act(async()=>{video.currentTime=499;video.dispatchEvent(new Event("seeking"));});
    expect(video.currentTime).toBe(499);
  });
  it("restores the last playback position when the live window cannot support seeking", async () => {
    hlsMock.supported=true;
    await act(async()=>root.render(<AtlasTheaterPlayer session={{...session,sourceType:"live",canSeek:false}}/>));await flush();
    const video=container.querySelector("video")!;
    await act(async()=>{video.currentTime=2;video.dispatchEvent(new Event("timeupdate"));});
    Object.defineProperties(video, {
      buffered:{configurable:true,value:{length:1,start:()=>0,end:()=>10}},
      seekable:{configurable:true,value:{length:1,start:()=>0,end:()=>10}}
    });
    await act(async()=>{video.currentTime=0;video.dispatchEvent(new Event("seeking"));});
    expect(video.currentTime).toBe(2);
  });
  it("reports unsupported playback when neither HLS path is available", async () => {
    vi.mocked(HTMLMediaElement.prototype.canPlayType).mockReturnValue("");
    await act(async()=>root.render(<AtlasTheaterPlayer session={session}/>));await flush();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("cannot play");
    expect(hlsMock.constructed).not.toHaveBeenCalled();
  });
  it("preserves paused position during caption replacement on managed HLS", async () => {
    hlsMock.supported=true;
    await act(async()=>root.render(<AtlasTheaterPlayer session={session} sessionResolver={async()=>({...session})}/>));await flush();
    const video=container.querySelector("video")!;
    await act(async()=>{video.currentTime=128;video.pause();});
    await act(async()=>{const select=container.querySelector("select")!;select.value="off";select.dispatchEvent(new Event("change",{bubbles:true}));});await flush();
    expect(video.currentTime).toBe(128);expect(video.paused).toBe(true);
    expect(hlsMock.destroy).toHaveBeenCalledTimes(1);
    expect(hlsMock.source).toHaveBeenCalledTimes(2);
  });
  it("does not advance or treat a stream error as episode completion", async () => {
    const next=vi.fn();
    await act(async()=>root.render(<AtlasTheaterPlayer session={session} onNextEpisode={next}/>));await flush();
    await act(async()=>container.querySelector("video")!.dispatchEvent(new Event("error")));
    expect(next).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("could not play");
  });
  it("changes captions while paused without playing or covering the native controls",async()=>{
    const resolver=vi.fn(async()=>({...session}));
    await act(async()=>root.render(<AtlasTheaterPlayer session={session} viewerId="user-a" sessionResolver={resolver}/>));await flush();
    const video=container.querySelector("video")!;
    await act(async()=>{video.currentTime=128;video.pause();});
    const previousCalls=play.mock.calls.length;
    await act(async()=>{const select=container.querySelector("select")!;select.value="3";select.dispatchEvent(new Event("change",{bubbles:true}));});await flush();
    expect(resolver).toHaveBeenCalledWith("jellyfin","e1",undefined,3);
    expect(video.currentTime).toBe(128);expect(video.paused).toBe(true);expect(play.mock.calls.length).toBe(previousCalls);
    expect(container.querySelector('.atlas-theater-video-shell [role="status"]')).toBeNull();
    await act(async()=>video.play());expect(video.paused).toBe(false);
  });
  it("keeps playing through caption replacement",async()=>{
    await act(async()=>root.render(<AtlasTheaterPlayer session={session} sessionResolver={async()=>({...session})}/>));await flush();
    const video=container.querySelector("video")!;video.currentTime=128;
    await act(async()=>{const select=container.querySelector("select")!;select.value="off";select.dispatchEvent(new Event("change",{bubbles:true}));});await flush();
    expect(video.currentTime).toBe(128);expect(video.paused).toBe(false);
  });
  it("offers a working Play button outside the video when autoplay is rejected",async()=>{
    blocked=true;await act(async()=>root.render(<AtlasTheaterPlayer session={session}/>));await flush();
    const button=Array.from(container.querySelectorAll("button")).find(x=>x.textContent==="Play")!;
    expect(button).toBeDefined();expect(button.closest(".atlas-theater-video-shell")).toBeNull();
    blocked=false;await act(async()=>button.click());expect(playing).toBe(true);expect(container.textContent).not.toContain("Playback is paused.");
  });
  it("advances only on ended and respects the automatic progression setting",async()=>{
    const next=vi.fn();await act(async()=>root.render(<AtlasTheaterPlayer session={session} onNextEpisode={next}/>));await flush();
    const video=container.querySelector("video")!;
    await act(async()=>video.dispatchEvent(new Event("timeupdate")));expect(next).not.toHaveBeenCalled();
    await act(async()=>video.dispatchEvent(new Event("ended",{bubbles:true})));expect(next).toHaveBeenCalledWith("e3");next.mockClear();
    await act(async()=>root.render(<AtlasTheaterPlayer session={session} onNextEpisode={next} autoAdvance={false}/>));
    await act(async()=>video.dispatchEvent(new Event("ended",{bubbles:true})));expect(next).not.toHaveBeenCalled();
  });
});
