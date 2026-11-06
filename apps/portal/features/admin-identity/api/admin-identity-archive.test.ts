import { expect, it, vi } from "vitest";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/services/authenticated", () => ({ authenticatedAtlasApiRequest: request }));
import { loadAdminInvitations } from "./admin-identity";

it("maps server lifecycle timestamps without replacing them with creation time", async () => {
  request.mockResolvedValue({
    items: [
      {
        invite_id: "example",
        role: "member",
        status: "completed",
        created_at: "2020-01-01T00:00:00Z",
        completed_at: "2026-11-06T12:00:00Z",
        revoked_at: null
      }
    ]
  });
  const [invitation] = await loadAdminInvitations();
  expect(invitation.completedAt).toBe("2026-11-06T12:00:00Z");
  expect(invitation.revokedAt).toBeNull();
  expect(invitation.createdAt).toBe("2020-01-01T00:00:00Z");
});
