import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { canMock, useAdminIdentityMock } = vi.hoisted(() => ({
  canMock: vi.fn<(permission: string) => boolean>(),
  useAdminIdentityMock: vi.fn()
}));

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
      '<section aria-labelledby="invitations-title">'
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
