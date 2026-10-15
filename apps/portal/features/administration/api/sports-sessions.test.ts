import { beforeEach, describe, expect, it, vi } from "vitest";
const request = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/services/authenticated", () => ({ authenticatedAtlasApiRequest: request }));
import { loadSportsSessionObservation } from "./sports-sessions";
const report = {observed_at: "2026-10-14T21:44:00Z", state_sha256: "a".repeat(64), ttl_seconds: 90,
  retained_count: 1, recent_count: 0, expired_count: 1,
  sessions: [{session_id: "owned", user_id: "viewer", target_id: "canary", age_seconds: 900,
    heartbeat_age_seconds: 900, heartbeat_expired: true}]};
describe("Sports session observation", () => {
  beforeEach(() => { request.mockReset(); });
  it("only issues authenticated no-store GET with cancellation", async () => {
    request.mockResolvedValue(report);const controller=new AbortController();
    expect(await loadSportsSessionObservation(controller.signal)).toEqual(report);
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith("/admin/live-sessions/sports", {
      method: "GET", cache: "no-store", signal: controller.signal,
    });
  });
  it.each([
    null, {...report, retained_count: 0}, {...report, expired_count: 0},
    {...report, sessions: [{...report.sessions[0], heartbeat_expired: false}]},
    {...report, sessions: [{...report.sessions[0], user_id: ""}]},
    {...report, state_sha256: "invalid"}, {...report, observed_at: "invalid"},
  ])("rejects incomplete or inconsistent state without inventing empty counts", async invalid => {
    request.mockResolvedValue(invalid);
    await expect(loadSportsSessionObservation()).rejects.toThrow("Sports session observation is unavailable.");
  });
  it("does not convert failure into an empty observation", async () => {
    request.mockRejectedValue(new Error("unavailable"));
    await expect(loadSportsSessionObservation()).rejects.toThrow("unavailable");
    expect(request).toHaveBeenCalledTimes(1);
  });
});
