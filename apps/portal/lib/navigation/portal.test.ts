import { describe, expect, it } from "vitest";

import type { AtlasEffectivePermissionPatterns } from "../authorization";
import {
  PORTAL_ROUTES,
  PORTAL_ROUTE_SECTIONS,
  portalNavigationSections,
  portalPageTitle,
  portalRouteForPathname,
  portalRouteMatchesPathname,
  portalRoutes,
  visiblePortalNavigationSections
} from "./portal";

function authorization(
  grantedPermissionPatterns: readonly string[],
  deniedPermissionPatterns: readonly string[] = []
): AtlasEffectivePermissionPatterns {
  return {
    grantedPermissionPatterns,
    deniedPermissionPatterns
  };
}

function visibleLabels(effective: AtlasEffectivePermissionPatterns): string[] {
  return visiblePortalNavigationSections(effective).flatMap((section) =>
    section.items.map((item) => item.label)
  );
}

describe("Portal route model", () => {
  it("registers every route ID exactly once", () => {
    expect(portalRoutes.map((route) => route.id)).toEqual([
      "home",
      "dashboard",
      "media",
      "library",
      "favorites",
      "requests",
      "sports",
      "theater",
      "downloads",
      "downloadManagement",
      "users",
      "services",
      "administration",
      "settings"
    ]);

    expect(new Set(portalRoutes.map((route) => route.id)).size).toBe(portalRoutes.length);
  });

  it("registers every route path exactly once", () => {
    expect(new Set(portalRoutes.map((route) => route.path)).size).toBe(portalRoutes.length);
  });

  it("provides stable named route access", () => {
    expect(PORTAL_ROUTES.home.path).toBe("/portal");
    expect(PORTAL_ROUTES.dashboard.path).toBe("/portal/administration/dashboard");
    expect(PORTAL_ROUTES.media.path).toBe("/portal/media");
    expect(PORTAL_ROUTES.library.path).toBe("/portal/library");
    expect(PORTAL_ROUTES.theater.path).toBe("/portal/theater");
    expect(PORTAL_ROUTES.media.navigationDescription).toBe("Browse and search movies and TV shows");
    expect(PORTAL_ROUTES.media.pageDescription).toBe(
      "Browse and search movies and TV shows available through Atlas."
    );
    expect(PORTAL_ROUTES.favorites.path).toBe("/portal/favorites");
    expect(PORTAL_ROUTES.favorites.permission).toBe("favorites.read");
    expect(PORTAL_ROUTES.users.permission).toBe("users.read");
  });

  it("derives ordered navigation sections from registered routes", () => {
    expect(
      portalNavigationSections.map((section) => ({
        label: section.label,
        routes: section.items.map((route) => route.id)
      }))
    ).toEqual([
      {
        label: PORTAL_ROUTE_SECTIONS.workspace,
        routes: ["home", "media", "favorites", "sports", "settings"]
      },
      {
        label: PORTAL_ROUTE_SECTIONS.management,
        routes: ["dashboard", "downloadManagement", "users", "services", "administration"]
      }
    ]);
  });

  it("keeps legacy Requests and Downloads routes registered but out of navigation", () => {
    expect(PORTAL_ROUTES.requests.path).toBe("/portal/requests");
    expect(PORTAL_ROUTES.downloads.path).toBe("/portal/downloads");
    expect(PORTAL_ROUTES.requests.navigation).toBe(false);
    expect(PORTAL_ROUTES.downloads.navigation).toBe(false);
    expect(PORTAL_ROUTES.library.navigation).toBe(false);
    expect(PORTAL_ROUTES.theater.navigation).toBe(false);
  });

  it("matches Home only at its exact path", () => {
    expect(portalRouteMatchesPathname(PORTAL_ROUTES.home, "/portal")).toBe(true);
    expect(portalRouteMatchesPathname(PORTAL_ROUTES.home, "/portal/media")).toBe(false);
  });

  it("matches feature roots and nested feature paths", () => {
    expect(portalRouteMatchesPathname(PORTAL_ROUTES.favorites, "/portal/favorites")).toBe(true);
    expect(portalRouteMatchesPathname(PORTAL_ROUTES.favorites, "/portal/favorites/example")).toBe(
      true
    );
    expect(portalRouteMatchesPathname(PORTAL_ROUTES.users, "/portal/settings")).toBe(false);
  });

  it("resolves the most specific matching route", () => {
    expect(portalRouteForPathname("/portal")).toBe(PORTAL_ROUTES.home);
    expect(portalRouteForPathname("/portal/administration/dashboard")).toBe(PORTAL_ROUTES.dashboard);
    expect(portalRouteForPathname("/portal/favorites/example")).toBe(PORTAL_ROUTES.favorites);
    expect(portalRouteForPathname("/portal/users/example")).toBe(PORTAL_ROUTES.users);
    expect(portalRouteForPathname("/not-a-portal-page")).toBeNull();
  });

  it("resolves Portal page titles through the route model", () => {
    expect(portalPageTitle("/portal")).toBe("Home");
    expect(portalPageTitle("/portal/favorites")).toBe("Favorites");
    expect(portalPageTitle("/portal/users/example")).toBe("Users");
    expect(portalPageTitle("/not-a-portal-page")).toBe("Portal");
  });
});

describe("Portal navigation authorization", () => {
  it("shows member-facing navigation from effective grants", () => {
    expect(
      visibleLabels(
        authorization([
          "media.read",
          "favorites.read",
          "requests.read",
          "users.self.read"
        ])
      )
    ).toEqual([
      "Home",
      "Media",
      "Favorites",
      "Settings"
    ]);
  });

  it("hides management navigation without effective grants", () => {
    const labels = visibleLabels(
      authorization([
        "media.read",
        "favorites.read",
        "requests.read",
        "users.self.read"
      ])
    );

    expect(labels).not.toContain("Users");
    expect(labels).not.toContain("Administration");
  });

  it("shows all current navigation through wildcard grants", () => {
    expect(visibleLabels(authorization(["*"]))).toEqual([
      "Home",
      "Media",
      "Favorites",
      "Sports",
      "Settings",
      "Admin Dashboard",
      "Download Management",
      "Users",
      "Services",
      "Administration"
    ]);
  });

  it("supports action wildcard navigation", () => {
    expect(visibleLabels(authorization(["*.read"]))).toEqual([
      "Home",
      "Media",
      "Favorites",
      "Sports",
      "Settings",
      "Admin Dashboard",
      "Users",
      "Services",
      "Administration"
    ]);
  });

  it("honors explicit denials before wildcard grants", () => {
    expect(
      visibleLabels(authorization(["*"], ["favorites.read", "users.read", "system.health.read"]))
    ).toEqual([
      "Home",
      "Media",
      "Sports",
      "Settings",
      "Admin Dashboard",
      "Download Management"
    ]);
  });

  it("uses favorites.read rather than favorites.write for navigation", () => {
    expect(visibleLabels(authorization(["favorites.read"], ["favorites.write"]))).toEqual([
      "Favorites"
    ]);
  });

  it("supports direct grants without role knowledge", () => {
    expect(visibleLabels(authorization(["system.health.read"]))).toEqual([
      "Services",
      "Administration"
    ]);
  });

  it("removes empty navigation sections", () => {
    expect(visiblePortalNavigationSections(authorization([]))).toEqual([]);
  });
});
