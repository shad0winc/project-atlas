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
