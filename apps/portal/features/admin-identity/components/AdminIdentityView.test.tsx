// @vitest-environment happy-dom
import { readFileSync } from "node:fs";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { canMock, useAdminIdentityMock } = vi.hoisted(() => ({
  canMock: vi.fn<(permission: string) => boolean>(),
  useAdminIdentityMock: vi.fn()
}));
vi.mock("../../administration/api/roles", () => ({ loadAssignableRoleCatalog: vi.fn().mockResolvedValue([]) }));

vi.mock("../../../lib/authorization", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../../../lib/authorization")>();

  return {
    ...actual,
    usePermission: () => ({
      grantedPermissionPatterns: [],
      deniedPermissionPatterns: [],
      can: canMock,
      canAny: () => false,
      canEvery: () => false
    })
  };
});

vi.mock("../hooks/use-admin-identity", () => ({
  useAdminIdentity: useAdminIdentityMock
}));

import { AdminIdentityView } from "./AdminIdentityView";

describe("AdminIdentityView surface spacing", () => {
  beforeEach(() => {
    canMock.mockReset();
    useAdminIdentityMock.mockReset();

    canMock.mockReturnValue(true);

    useAdminIdentityMock.mockReturnValue({
      state: {
        status: "ready",
        users: [
          {
            userId: "usr_example",
            username: "example",
            displayName: "Example User",
            status: "active",
            roles: ["user"]
          }
        ],
        invitations: []
      },
      refresh: vi.fn(),
      selectedUser: null,
      detailLoading: false,
      inspectUser: vi.fn(),
      clearSelectedUser: vi.fn(),
      mutateUser: vi.fn(),
      createInvitation: vi.fn(),
      revokeInvitation: vi.fn(),
      mutationError: null,
      createdToken: null,
      clearCreatedToken: vi.fn(),
      busyKey: null
    });
  });

  it("uses the padded administrative card surface for user rows", () => {
    const markup = renderToStaticMarkup(<AdminIdentityView />);

    expect(markup).toContain(
      'class="card admin-identity-card"'
    );
    expect(markup).toContain("Example User");
  });
  it("shows invitation controls without user management in the Administration panel", () => {
    const markup = renderToStaticMarkup(<AdminIdentityView invitationsOnly />);
    expect(markup).toContain("Invitations");
    expect(markup).toContain("Customize invitation email");
    expect(markup).not.toContain("User accounts");
    expect(markup).not.toContain("Example User");
  });

  it("lets an administrator inspect archived history and moves a revoked row at the 24-hour cutoff", async () => {
    vi.useFakeTimers();
    const now = Date.parse("2026-11-07T12:00:00Z");
    vi.setSystemTime(now);
    const current = useAdminIdentityMock.getMockImplementation()!();
    current.state.invitations = [
      { inviteId: "pending", email: "pending@example.invalid", status: "pending", role: "member" },
      { inviteId: "old", email: "old@example.invalid", status: "completed", role: "member", completedAt: "2020-01-01T00:00:00Z" },
      { inviteId: "recent", email: "recent@example.invalid", status: "revoked", role: "member", revokedAt: new Date(now - 24 * 60 * 60 * 1000 + 60_000).toISOString() }
    ];
    useAdminIdentityMock.mockReturnValue(current);
    const container = document.createElement("div");
    const root = createRoot(container);
    const button = (label: string) => [...container.querySelectorAll("button")].find((item) => item.textContent === label)!;
    try {
      await act(async () => { root.render(<AdminIdentityView invitationsOnly />); });
      expect(container.textContent).toContain("Current (2)");
      expect(container.textContent).not.toContain("old@example.invalid");
      await act(async () => { button("Archived (1)").click(); });
      expect(container.textContent).toContain("old@example.invalid");
      expect(container.textContent).not.toContain("pending@example.invalid");
      await act(async () => { button("Current (2)").click(); vi.advanceTimersByTime(60_000); });
      expect(container.textContent).toContain("Current (1)");
      expect(container.textContent).toContain("Archived (2)");
      expect(container.textContent).not.toContain("recent@example.invalid");
    } finally {
      await act(async () => { root.unmount(); });
      vi.useRealTimers();
    }
  });
  it("does not expose a free-text role editor", () => {
    const source = readFileSync(
      join(
        process.cwd(),
        "features/admin-identity/components/AdminIdentityView.tsx"
      ),
      "utf8"
    );
    expect(source).not.toContain('.split(",")');
    expect(source).toContain("assignableRoles.map");
  });

  it("renders selected user management inline with the matching user card", () => {
    const source = readFileSync(
      join(
        process.cwd(),
        "features/admin-identity/components/AdminIdentityView.tsx"
      ),
      "utf8"
    );

    const mapStart = source.indexOf("{state.users.map((user) => {");
    const invitationsStart = source.indexOf(
      'aria-labelledby="invitations-title"'
    );

    expect(mapStart).toBeGreaterThan(-1);
    expect(invitationsStart).toBeGreaterThan(mapStart);

    const userListSource = source.slice(mapStart, invitationsStart);

    expect(userListSource).toContain(
      "const isSelected = selectedUser?.userId === user.userId;"
    );
    expect(userListSource).toContain("{isSelected && selectedUser ? (");
    expect(userListSource).toContain("<UserDetail");
    expect(userListSource).toContain("Manage {user.displayName}");
    expect(source).toContain('className="admin-identity-inline-detail"');
    expect(source).not.toContain("View {user.displayName}");
    expect(source).not.toContain("key={selectedUser.userId}");
  });

  it("does not make the assignable-role effect depend on the unstable can callback", () => {
    const source = readFileSync(
      join(
        process.cwd(),
        "features/admin-identity/components/AdminIdentityView.tsx"
      ),
      "utf8"
    );

    expect(source).toContain(
      "const canAssignRoles = can(ATLAS_PERMISSIONS.rolesAssign);"
    );
    expect(source).toContain("if (!canAssignRoles) return;");
    expect(source).toContain("}, [canAssignRoles]);");
    expect(source).not.toContain("}, [can]);");
  });

});

describe("PR107 user lifecycle controls", () => {
  const source = readFileSync(
    join(
      process.cwd(),
      "features/admin-identity/components/AdminIdentityView.tsx"
    ),
    "utf8"
  );

  it("marks the required create-user identity fields", () => {
    expect(source).toContain("<span>Username <span aria-hidden=\"true\">*</span></span>");
    expect(source).toContain("<span>Display Name <span aria-hidden=\"true\">*</span></span>");
    expect(source).toContain("<span>Email Address <span aria-hidden=\"true\">*</span></span>");
    expect(source).toContain("<span>Password <span aria-hidden=\"true\">*</span></span>");
  });

  it("exposes contact and notification controls", () => {
    expect(source).toContain("Discord Account");
    expect(source).toContain("Email notifications");
    expect(source).toContain("Discord notifications");
  });

  it("keeps username read-only while allowing profile edits", () => {
    expect(source).toContain("readOnly");
    expect(source).toContain("Save account");
    expect(source).toContain("First Name");
    expect(source).toContain("Last Name");
  });

  it("provides a dedicated password action", () => {
    expect(source).toContain("Set New Password");
    expect(source).toContain("setUserPassword");
    expect(source).toContain("Atlas does not store the password");
  });
});
