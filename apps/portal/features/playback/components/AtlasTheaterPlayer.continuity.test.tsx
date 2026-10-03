// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { AtlasTheaterPlayer } from "./AtlasTheaterPlayer";
import type { PlaybackSession } from "../types/session";
vi.mock("../services/stream", () => ({ bootstrapPlaybackStream: async () => ({ streamUrl: "https://playback.example.test/videos/fixture/master.m3u8" }) }));
const session: PlaybackSession = {available:true,action:"watch_now",label:"Watch Now",backend:"jellyfin",sourceType:"library",provider:"jellyfin",requestedTargetId:"e1",playableTargetId:"e1",title:"Fixture",mediaType:"tv",canSeek:true,playbackBootstrapUrl:"",playbackCapability:"fixture",audioTracks:[],subtitleTracks:[{index:3,kind:"subtitle",label:"Signs & Songs",default:false,forced:false}],seriesId:"s1",nextTargetId:"e3"};
let root: Root;
let container: HTMLDivElement;
let playing: boolean;
let blocked: boolean;
let play: Mock<() => Promise<void>>;
async function flush() { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); }
beforeEach(() => {
  Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
  playing=false; blocked=false;
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
