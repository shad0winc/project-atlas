import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Portal landing contract", () => {
  const home = readFileSync("app/(protected)/portal/page.tsx", "utf8");
  const admin = readFileSync("app/(protected)/portal/administration/dashboard/page.tsx", "utf8");

  it("opens Home for authenticated users with the self-read grant", () => {
    expect(home).toContain("permission={PORTAL_ROUTES.home.permission}");
    expect(home).toContain("<PortalHome key={user.user_id}");
    expect(home).not.toContain("router.replace");
  });

  it("retains the system dashboard behind its existing effective permission", () => {
    expect(admin).toContain("const route = PORTAL_ROUTES.dashboard;");
    expect(admin).toContain("permission={route.permission}");
    expect(admin).toContain("<PortalDashboardView />");
  });
});
