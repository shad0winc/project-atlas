import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
const test = vi.hoisted(() => ({allowed: true, state: {status: "loading"} as unknown}));
vi.mock("../../../lib/authorization", () => ({ ATLAS_PERMISSIONS: {liveSessionsManage: "atlas.live_sessions.manage"},
  usePermission: () => ({can: () => test.allowed})}));
vi.mock("../hooks/use-sports-session-observation", () => ({useSportsSessionObservation: () => ({state: test.state, refresh: vi.fn()})}));
import { SportsSessionStatus } from "./SportsSessionStatus";
describe("SportsSessionStatus", () => {
  beforeEach(() => {test.allowed=true;test.state={status: "loading"};});
  it("is hidden without the management permission", () => {
    test.allowed=false;expect(renderToStaticMarkup(<SportsSessionStatus />)).toBe("");
  });
  it("shows retained expired ownership with no reset mutation action", () => {
    test.state={status: "ready", report: {observed_at: "2026-10-14T21:44:00Z", recent_count: 0, expired_count: 1, retained_count: 1,
      sessions: [{session_id: "owned", user_id: "viewer", target_id: "canary", heartbeat_age_seconds: 900, heartbeat_expired: true}]}};
    const html=renderToStaticMarkup(<SportsSessionStatus />);
    expect(html).toContain("Refresh session status");expect(html).toContain("1 retained total");
    expect(html).toContain("Expired heartbeat; recovery review needed");
    expect(html).toContain("does not prove playback has stopped");
    expect(html).not.toContain("release-capability");expect(html).not.toContain("Reset");
  });
  it("reports unavailable rather than empty on an error", () => {
    test.state={status:"error"};const html=renderToStaticMarkup(<SportsSessionStatus />);
    expect(html).toContain("status is unavailable");expect(html).not.toContain("No retained Sports sessions");
  });
});
