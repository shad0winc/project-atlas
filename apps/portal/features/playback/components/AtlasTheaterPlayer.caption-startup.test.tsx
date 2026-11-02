// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AtlasTheaterPlayer } from "./AtlasTheaterPlayer";
import type { PlaybackSession } from "../types/session";
import type { LoaderConfig } from "hls.js";

const mock = vi.hoisted(() => ({ instances: [] as Array<{
  config: { fragLoadPolicy: { default: LoaderConfig } };
  handlers: Map<string, (event: string, data: {frag: {type: string; sn: number; start: number; duration: number}}) => void>;
  destroyed: boolean;
}> }));
vi.mock("../services/stream", () => ({ bootstrapPlaybackStream: async () => ({streamUrl:"https://playback.example.test/master.m3u8"}) }));
vi.mock("hls.js", () => ({default: class {
  static DefaultConfig = {fragLoadPolicy: {default: {maxTimeToFirstByteMs:10000,maxLoadTimeMs:120000,timeoutRetry:{maxNumRetry:4,retryDelayMs:0,maxRetryDelayMs:0},errorRetry:{maxNumRetry:6,retryDelayMs:1000,maxRetryDelayMs:8000}}}};
  static Events = {FRAG_LOADED:"loaded",FRAG_BUFFERED:"buffered",ERROR:"error"};
  static isSupported() {return true;}
  config; handlers = new Map(); destroyed=false;
  constructor(options: {fragLoadPolicy?: {default: LoaderConfig}}) {
    this.config={fragLoadPolicy:options.fragLoadPolicy ?? structuredClone(thisDefault())};
    mock.instances.push(this);
  }
  on(event: string,callback: unknown) {this.handlers.set(event,callback);}
  attachMedia() {} loadSource() {} destroy() {this.destroyed=true;}
} }));
function thisDefault() {return {default:{maxTimeToFirstByteMs:10000,maxLoadTimeMs:120000,timeoutRetry:{maxNumRetry:4,retryDelayMs:0,maxRetryDelayMs:0},errorRetry:{maxNumRetry:6,retryDelayMs:1000,maxRetryDelayMs:8000}}};}
const session: PlaybackSession={available:true,action:"watch_now",label:"Watch Now",backend:"jellyfin",sourceType:"library",provider:"jellyfin",requestedTargetId:"fixture",playableTargetId:"fixture",title:"Fixture",mediaType:"movie",canSeek:true,playbackBootstrapUrl:"",playbackCapability:"fixture",audioTracks:[],subtitleTracks:[{index:7,kind:"subtitle",codec:"subrip",label:"English",default:false,forced:false}]};
let root:Root,container:HTMLDivElement;
beforeEach(()=>{
  Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});mock.instances.length=0;
  vi.spyOn(HTMLMediaElement.prototype,"canPlayType").mockReturnValue("");
  vi.spyOn(HTMLMediaElement.prototype,"load").mockImplementation(()=>undefined);
  container=document.createElement("div");document.body.append(container);root=createRoot(container);
});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();vi.restoreAllMocks();});
async function flush(){await act(async()=>{await Promise.resolve();await Promise.resolve();});}
async function select(value:string,sourceType:"library"|"live"="library"){
  const original={...session,sourceType};const resolve=vi.fn(async()=>({...original,playbackCapability:"selected"}));
  await act(async()=>root.render(<AtlasTheaterPlayer session={original} sessionResolver={resolve}/>));await flush();
  const menu=container.querySelector("select")!;
  await act(async()=>{menu.value=value;menu.dispatchEvent(new Event("change",{bubbles:true}));});await flush();
  return {resolve,instance:mock.instances.at(-1)!};
}
it("reproduces the old ten-second first-fragment limit and allows one bounded cold caption load",async()=>{
  const {instance,resolve}=await select("7");
  expect(mock.instances[0].config.fragLoadPolicy.default.maxTimeToFirstByteMs).toBe(10000);
  expect(instance.config.fragLoadPolicy.default).toMatchObject({maxTimeToFirstByteMs:120000,maxLoadTimeMs:120000,timeoutRetry:null,errorRetry:null});
  expect(resolve).toHaveBeenCalledTimes(1);expect(container.textContent).toContain("Preparing captions…");
  expect(container.querySelector("select")!.disabled).toBe(true);
});
it("restores normal limits after main video arrives, without opening another playback session",async()=>{
  const {instance,resolve}=await select("7");
  const loaded=instance.handlers.get("loaded")!;
  await act(async()=>loaded("loaded",{frag:{type:"audio",sn:0,start:0,duration:3}}));
  expect(instance.config.fragLoadPolicy.default.maxTimeToFirstByteMs).toBe(120000);
  await act(async()=>loaded("loaded",{frag:{type:"main",sn:0,start:0,duration:3}}));
  expect(instance.config.fragLoadPolicy.default.maxTimeToFirstByteMs).toBe(10000);
  expect(instance.config.fragLoadPolicy.default.timeoutRetry?.maxNumRetry).toBe(4);
  expect(container.textContent).not.toContain("Preparing captions…");expect(resolve).toHaveBeenCalledTimes(1);
});
it.each(["off","auto"])("keeps normal limits when captions are %s",async(value)=>{
  const {instance}=await select(value);expect(instance.config.fragLoadPolicy.default.maxTimeToFirstByteMs).toBe(10000);
});
it("keeps normal fragment limits for Sports",async()=>{
  const {instance}=await select("7","live");expect(instance.config.fragLoadPolicy.default.maxTimeToFirstByteMs).toBe(10000);
});
it("does not change a disposed stream when its first fragment arrives late",async()=>{
  const {instance}=await select("7");const loaded=instance.handlers.get("loaded")!;
  await act(async()=>root.render(null));
  await act(async()=>loaded("loaded",{frag:{type:"main",sn:0,start:0,duration:3}}));
  expect(instance.destroyed).toBe(true);expect(instance.config.fragLoadPolicy.default.maxTimeToFirstByteMs).toBe(120000);
});
