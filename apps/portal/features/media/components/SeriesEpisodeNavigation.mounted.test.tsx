// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { SeriesEpisodeNavigation } from "./SeriesEpisodeNavigation";
vi.mock("next/link",()=>({default:({children,...props}:{children:React.ReactNode;href:string})=><a {...props}>{children}</a>}));
vi.mock("../../playback/services/session",()=>({resolveSeriesEpisodes:async()=>[
 {id:"e1",title:"First",seasonNumber:1,episodeNumber:1},
 {id:"e3",title:"Third",seasonNumber:1,episodeNumber:3},
 {id:"s2e1",title:"Next season",seasonNumber:2,episodeNumber:1}
]}));
it("opens on the current episode and allows switching season and exact episode",async()=>{
 Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
 const container=document.createElement("div");document.body.append(container);const root=createRoot(container);
 try {
  await act(async()=>root.render(<SeriesEpisodeNavigation provider="jellyfin" seriesId="s1" currentEpisodeId="s2e1" title="This series"/>));
  await act(async()=>container.querySelector("button")!.click());
  let selects=container.querySelectorAll("select");expect(selects[0].value).toBe("2");expect(selects[1].value).toBe("s2e1");
  await act(async()=>{selects[0].value="1";selects[0].dispatchEvent(new Event("change",{bubbles:true}));});
  selects=container.querySelectorAll("select");expect(selects[1].value).toBe("e1");
  await act(async()=>{selects[1].value="e3";selects[1].dispatchEvent(new Event("change",{bubbles:true}));});
  expect(container.querySelector("a")!.getAttribute("href")).toBe("/portal/theater?provider=jellyfin&item=e3");
 } finally {await act(async()=>root.unmount());container.remove();}
});
