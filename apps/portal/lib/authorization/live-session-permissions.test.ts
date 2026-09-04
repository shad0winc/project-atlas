import { describe, expect, it } from "vitest";
import { ATLAS_PERMISSIONS } from "./permissions";

describe("Live-session administration permission", () => {
  it("publishes the dedicated management permission", () => {
    expect(ATLAS_PERMISSIONS.liveSessionsManage).toBe("atlas.live_sessions.manage");
  });
});
