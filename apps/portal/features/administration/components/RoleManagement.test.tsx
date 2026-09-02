import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const { can, useAdminRolesMock } = vi.hoisted(() => ({
  can: vi.fn<(permission: string) => boolean>(() => true),
  useAdminRolesMock: vi.fn()
}));

vi.mock("../../../lib/authorization", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../lib/authorization")>()),
  usePermission: () => ({ grantedPermissionPatterns: [], deniedPermissionPatterns: [], can, canAny: () => false, canEvery: () => false })
}));
vi.mock("../hooks/use-admin-roles", () => ({ useAdminRoles: useAdminRolesMock }));

import { RoleManagement } from "./RoleManagement";

describe("RoleManagement", () => {
  it("renders protected service roles and bounded custom-role creation", () => {
    useAdminRolesMock.mockReturnValue({
      state: { status: "ready", catalog: {
        permissions: ["sports.read", "sports.events.request"],
        roles: [{ name: "sports_admin", displayName: "Sports Administrator", description: "Sports", permissions: ["sports.read", "sports.events.request"], protected: true, assignable: true, source: "built-in" }]
      }},
      refresh: vi.fn(), mutationError: null, busyKey: null,
      createRole: vi.fn(), updateRole: vi.fn(), removeRole: vi.fn()
    });
    const markup = renderToStaticMarkup(<RoleManagement />);
    expect(markup).toContain("Roles and permissions");
    expect(markup).toContain("Sports Administrator");
    expect(markup).toContain("Built-in role");
    expect(markup).toContain("Create role");
  });
});
