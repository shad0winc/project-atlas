import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("role assignment contract", () => {
  it("uses narrow discovery and removes legacy invitation roles", () => {
    const s=fs.readFileSync(path.resolve(process.cwd(), "features/admin-identity/components/AdminIdentityView.tsx"), "utf8");
    expect(s).toContain("loadAssignableRoleCatalog");
    expect(s).toContain("Retained protected/nonassignable role");
    expect(s).not.toContain('<option value="user">User</option>');
    expect(s).not.toContain('<option value="admin">Admin</option>');
  });
  it("gates management catalog fetch", () => {
    const s=fs.readFileSync(path.resolve(process.cwd(), "features/administration/components/RoleManagement.tsx"), "utf8");
    expect(s).toContain("useAdminRoles(canRead)");
  });
});
