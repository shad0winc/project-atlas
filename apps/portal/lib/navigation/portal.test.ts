import { describe, expect, it } from "vitest";

import { portalPageTitle, visiblePortalNavigationSections } from "./portal";

function visibleLabels(roles: readonly string[]): string[] {
  return visiblePortalNavigationSections(roles).flatMap((section) =>
    section.items.map((item) => item.label)
  );
}

describe("Portal navigation authorization", () => {
  it("shows member-facing navigation to members", () => {
    expect(visibleLabels(["member"])).toEqual(["Dashboard", "Media", "Requests", "Settings"]);
  });

  it("hides management navigation from members", () => {
    expect(visibleLabels(["member"])).not.toContain("Users");
    expect(visibleLabels(["member"])).not.toContain("Administration");
  });

  it("shows all current navigation to global administrators", () => {
    expect(visibleLabels(["global_admin"])).toEqual([
      "Dashboard",
      "Media",
      "Requests",
      "Downloads",
      "Users",
      "Administration",
      "Settings"
    ]);
  });

  it("supports read-only wildcard navigation", () => {
    expect(visibleLabels(["read_only"])).toEqual([
      "Dashboard",
      "Media",
      "Requests",
      "Downloads",
      "Users",
      "Administration",
      "Settings"
    ]);
  });

  it("removes empty navigation sections", () => {
    expect(visiblePortalNavigationSections(["unknown_role"])).toEqual([]);
  });

  it("resolves Portal page titles independently from visibility", () => {
    expect(portalPageTitle("/portal")).toBe("Dashboard");
    expect(portalPageTitle("/portal/users/example")).toBe("Users");
    expect(portalPageTitle("/not-a-portal-page")).toBe("Portal");
  });
});
