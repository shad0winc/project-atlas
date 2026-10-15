// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
const request=vi.hoisted(() => vi.fn());
vi.mock("../../../lib/services/authenticated", () => ({authenticatedAtlasApiRequest: request}));
vi.mock("../../../lib/auth/use-auth", () => ({useAuth: () => ({isAuthenticated: true})}));
import { useSportsSessionObservation } from "./use-sports-session-observation";
const report={observed_at:"2026-10-14T21:44:00Z",state_sha256:"a".repeat(64),ttl_seconds:90,
  retained_count:0,recent_count:0,expired_count:0,sessions:[]};
function Probe({enabled}: {enabled:boolean}) {
  const {state,refresh}=useSportsSessionObservation(enabled);
  return <button onClick={refresh}>{state.status}</button>;
}
describe("mounted Sports status refresh", () => {
  it("refreshes through GET only and suppresses unauthorized observation", async () => {
    request.mockReset();request.mockResolvedValue(report);
    const node=document.createElement("div");document.body.append(node);const root=createRoot(node);
    try {
      await act(async () => root.render(<Probe enabled={false}/>));expect(request).not.toHaveBeenCalled();
      await act(async () => root.render(<Probe enabled={true}/>));expect(node.textContent).toBe("ready");
      await act(async () => node.querySelector("button")!.click());expect(node.textContent).toBe("ready");
      expect(request).toHaveBeenCalledTimes(2);
      for(const [,options] of request.mock.calls) expect(options.method).toBe("GET");
    } finally {await act(async () => root.unmount());node.remove();}
  });
});
