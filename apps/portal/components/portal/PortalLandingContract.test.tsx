import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("Portal landing contract", () => {
  const source = readFileSync(
    resolve(
      process.cwd(),
      "app/(protected)/portal/page.tsx"
    ),
    "utf8"
  );

  it("uses effective permissions instead of role names", () => {
    expect(source).toContain(
      'import { usePermission } from "../../../lib/authorization/use-permission";'
    );
    expect(source).toContain(
      "const { can } = usePermission();"
    );
    expect(source).toContain(
      "const canViewDashboard = can(dashboardRoute.permission);"
    );
    expect(source).toContain(
      "const canViewMedia = can(mediaRoute.permission);"
    );

    expect(source).not.toContain(
      'roles.includes("member")'
    );
    expect(source).not.toContain(
      'roles.includes("global_admin")'
    );
  });

  it("opens Media when dashboard access is unavailable", () => {
    expect(source).toContain(
      "const shouldOpenMedia = !canViewDashboard && canViewMedia;"
    );
    expect(source).toContain(
      "router.replace(mediaRoute.path);"
    );
  });

  it("preserves the dashboard for authorized users", () => {
    expect(source).toContain(
      "<PortalDashboardView />"
    );
    expect(source).toContain(
      "permission={dashboardRoute.permission}"
    );
  });
});
