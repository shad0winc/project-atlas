// @vitest-environment happy-dom
import { act, useEffect } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const { users, invitations } = vi.hoisted(() => ({ users: vi.fn(), invitations: vi.fn() }));
vi.mock("../../../lib/auth/use-auth", () => ({ useAuth: () => ({ isAuthenticated: true }) }));
vi.mock("../api/admin-identity", () => ({
  loadAdminUsers: users,
  loadAdminInvitations: invitations,
  createAdminInvitation: vi.fn(),
  createAdminUser: vi.fn(),
  loadAdminUser: vi.fn(),
  revokeAdminInvitation: vi.fn(),
  setAdminUserPassword: vi.fn(),
  updateAdminUser: vi.fn()
}));
import { useAdminIdentity } from "./use-admin-identity";
let latest: ReturnType<typeof useAdminIdentity>;
function Harness() {
  const identity = useAdminIdentity();
  useEffect(() => { latest = identity; });
  return <p>{identity.state.status}</p>;
}
let root: Root;

describe("invitation background refresh", () => {
  beforeEach(async () => {
    vi.useFakeTimers();
    users.mockReset().mockResolvedValue([]);
    invitations.mockReset().mockResolvedValue([]);
    root = createRoot(document.createElement("div"));
    await act(async () => {
      root.render(<Harness />);
    });
  });
  afterEach(async () => {
    await act(async () => {
      root.unmount();
    });
    vi.useRealTimers();
  });

  it("refreshes invitation lifecycle status without reloading users or leaving ready state", async () => {
    const accepted = {
      inviteId: "accepted",
      status: "completed",
      completedAt: "2026-11-06T12:00:00Z"
    };
    invitations.mockResolvedValueOnce([accepted]);
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });
    expect(users).toHaveBeenCalledTimes(1);
    expect(invitations).toHaveBeenCalledTimes(2);
    expect(latest.state).toMatchObject({ status: "ready", invitations: [accepted] });
    expect(latest.invitationRefreshError).toBeNull();
  });

  it("keeps existing data and exposes a failed refresh, then recovers on focus", async () => {
    invitations.mockRejectedValueOnce(new Error("offline"));
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });
    expect(latest.state.status).toBe("ready");
    expect(latest.invitationRefreshError?.message).toBe("offline");
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
    });
    expect(latest.invitationRefreshError).toBeNull();
  });
});
