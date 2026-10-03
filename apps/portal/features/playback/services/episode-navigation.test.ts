import { describe, expect, it } from "vitest";
import { episodeHref, nextEpisodeTarget } from "./episode-navigation";
import type { PlaybackSession } from "../types/session";
const session: PlaybackSession = { available:true, action:"watch_now",label:"Watch Now",backend:"jellyfin",sourceType:"library",provider:"jellyfin",requestedTargetId:"e1",playableTargetId:"e1",title:"Episode",mediaType:"tv",canSeek:true,playbackBootstrapUrl:"",playbackCapability:"",audioTracks:[],subtitleTracks:[],seriesId:"verified-series",nextTargetId:"e3" };
describe("episode progression",()=>{
  it("uses the next verified inventory item rather than episode arithmetic",()=>expect(nextEpisodeTarget(session,true)).toBe("e3"));
  it("does not advance when disabled or at the final episode",()=>{expect(nextEpisodeTarget(session,false)).toBeNull();expect(nextEpisodeTarget({...session,nextTargetId:undefined},true)).toBeNull();});
  it("does not loop or advance movies, live sessions or unverified series",()=>{
    for(const change of [{nextTargetId:"e1"},{sourceType:"live" as const},{seriesId:undefined},{available:false}]) expect(nextEpisodeTarget({...session,...change},true)).toBeNull();
  });
  it("encodes item identities without inserting another URL",()=>expect(episodeHref("jellyfin","a&item=other")).toBe("/portal/theater?provider=jellyfin&item=a%26item%3Dother"));
});
