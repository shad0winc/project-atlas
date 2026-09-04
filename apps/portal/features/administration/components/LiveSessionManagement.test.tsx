import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const can = vi.fn<(permission: string) => boolean>();

vi.mock("../../../lib/authorization", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../lib/authorization")>();
  return {
    ...actual,
    usePermission: () => ({
      grantedPermissionPatterns: [],
      deniedPermissionPatterns: [],
      can,
      canAny: () => false,
      canEvery: () => false
    })
  };
});

vi.mock("../hooks/use-admin-live-sessions", () => ({
  useAdminLiveSessions: () => ({
    state: {
      status: "ready",
      policy: {
        version: 1,
        defaultLimit: 5,
        ttlSeconds: 90,
        users: [
          {
            userId: "usr-target",
            username: "target-user",
            displayName: "Target User",
            overrideLimit: 2,
            effectiveLimit: 2,
            activeCount: 1,
            sessions: [{
              sessionId: "session-safe",
              targetId: "sports-event-001",
              ageSeconds: 40,
              heartbeatAgeSeconds: 15
            }]
          }
        ]
      }
    },
    refresh: vi.fn(),
    mutationError: null,
    busyKey: null,
    setDefaultLimit: vi.fn(),
    setUserOverride: vi.fn(),
    clearUserOverride: vi.fn()
  })
}));

import { LiveSessionManagement } from "./LiveSessionManagement";

describe("LiveSessionManagement", () => {
  beforeEach(() => can.mockReset());

  it("is hidden without the dedicated management permission", () => {
    can.mockReturnValue(false);
    expect(renderToStaticMarkup(<LiveSessionManagement />)).toBe("");
  });

  it("renders safe policy and active-session information", () => {
    can.mockImplementation((permission) => permission === "atlas.live_sessions.manage");
    const markup = renderToStaticMarkup(<LiveSessionManagement />);
    expect(markup).toContain("Live-session concurrency");
    expect(markup).toContain("Default Live-session limit");
    expect(markup).toContain("Target User");
    expect(markup).toContain("1 active / 2 allowed");
    expect(markup).toContain("sports-event-001");
    expect(markup).toContain("session-safe");
    expect(markup).toContain("Default");
    for (const forbidden of [
      "stream_path",
      "playback_capability",
      "jellyfin_item_id",
      "jellyfin_user_id",
      "access_token",
      "authorization",
      "created_at",
      "last_seen_at"
    ]) {
      expect(markup.toLowerCase()).not.toContain(forbidden);
    }
  });
});
