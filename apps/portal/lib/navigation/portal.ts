import {
  ATLAS_PERMISSIONS,
  hasAtlasPermission,
  type AtlasEffectivePermissionPatterns,
  type AtlasPermission
} from "../authorization/permissions";

export const PORTAL_ROUTE_SECTIONS = {
  workspace: "Workspace",
  management: "Management"
} as const;

export type PortalRouteSection = (typeof PORTAL_ROUTE_SECTIONS)[keyof typeof PORTAL_ROUTE_SECTIONS];

export type PortalRouteId =
  | "dashboard"
  | "media"
  | "favorites"
  | "requests"
  | "downloads"
  | "users"
  | "services"
  | "administration"
  | "settings";

/**
 * Stable route metadata shared by Portal navigation and page presentation.
 *
 * Next.js App Router files remain responsible for implementing routes and
 * browser metadata. This model centralizes only application-level route
 * identity, matching, presentation metadata, and required permissions.
 */
export type PortalRoute = Readonly<{
  id: PortalRouteId;
  path: string;
  label: string;
  navigationDescription: string;
  abbreviation: string;
  permission: AtlasPermission;
  section: PortalRouteSection;
  pageDescription?: string;
}>;

export type PortalNavigationSection = Readonly<{
  label: PortalRouteSection;
  items: readonly PortalRoute[];
}>;

export const portalRoutes: readonly PortalRoute[] = [
  {
    id: "dashboard",
    path: "/portal",
    label: "Dashboard",
    navigationDescription: "Atlas system overview",
    abbreviation: "DB",
    permission: ATLAS_PERMISSIONS.dashboardRead,
    section: PORTAL_ROUTE_SECTIONS.workspace,
    pageDescription: "Review the current state of your Project Atlas environment."
  },
  {
    id: "media",
    path: "/portal/media",
    label: "Media",
    navigationDescription: "Browse and search movies and TV shows",
    abbreviation: "ME",
    permission: ATLAS_PERMISSIONS.mediaRead,
    section: PORTAL_ROUTE_SECTIONS.workspace,
    pageDescription: "Browse and search movies and TV shows available through Atlas."
  },
  {
    id: "favorites",
    path: "/portal/favorites",
    label: "Favorites",
    navigationDescription: "Your saved media",
    abbreviation: "FV",
    permission: ATLAS_PERMISSIONS.favoritesRead,
    section: PORTAL_ROUTE_SECTIONS.workspace,
    pageDescription: "Review and manage media saved to your personal Favorites list."
  },
  {
    id: "requests",
    path: "/portal/requests",
    label: "Requests",
    navigationDescription: "Media requests and approvals",
    abbreviation: "RQ",
    permission: ATLAS_PERMISSIONS.requestsRead,
    section: PORTAL_ROUTE_SECTIONS.workspace
  },
  {
    id: "downloads",
    path: "/portal/downloads",
    label: "Downloads",
    navigationDescription: "Download activity and status",
    abbreviation: "DL",
    permission: ATLAS_PERMISSIONS.monitoringRead,
    section: PORTAL_ROUTE_SECTIONS.workspace
  },
  {
    id: "users",
    path: "/portal/users",
    label: "Users",
    navigationDescription: "Accounts and access",
    abbreviation: "US",
    permission: ATLAS_PERMISSIONS.usersRead,
    section: PORTAL_ROUTE_SECTIONS.management
  },
  {
    id: "services",
    path: "/portal/services",
    label: "Services",
    navigationDescription: "Managed service health and details",
    abbreviation: "SV",
    permission: ATLAS_PERMISSIONS.systemHealthRead,
    section: PORTAL_ROUTE_SECTIONS.management,
    pageDescription: "Review Atlas-managed service health and read-only runtime details."
  },
  {
    id: "administration",
    path: "/portal/administration",
    label: "Administration",
    navigationDescription: "Services and configuration",
    abbreviation: "AD",
    permission: ATLAS_PERMISSIONS.systemHealthRead,
    section: PORTAL_ROUTE_SECTIONS.management
  },
  {
    id: "settings",
    path: "/portal/settings",
    label: "Settings",
    navigationDescription: "Portal preferences",
    abbreviation: "ST",
    permission: ATLAS_PERMISSIONS.usersSelfRead,
    section: PORTAL_ROUTE_SECTIONS.management
  }
];

function routeById(routeId: PortalRouteId): PortalRoute {
  const route = portalRoutes.find((candidate) => candidate.id === routeId);

  if (!route) {
    throw new Error(`Portal route is not registered: ${routeId}`);
  }

  return route;
}

export const PORTAL_ROUTES = {
  dashboard: routeById("dashboard"),
  media: routeById("media"),
  favorites: routeById("favorites"),
  requests: routeById("requests"),
  downloads: routeById("downloads"),
  users: routeById("users"),
  services: routeById("services"),
  administration: routeById("administration"),
  settings: routeById("settings")
} as const satisfies Readonly<Record<PortalRouteId, PortalRoute>>;

/**
 * Determine whether a pathname belongs to a registered Portal route.
 *
 * The dashboard route matches only `/portal`, while feature routes also match
 * nested detail paths beneath their registered root.
 */
export function portalRouteMatchesPathname(route: PortalRoute, pathname: string): boolean {
  if (route.path === PORTAL_ROUTES.dashboard.path) {
    return pathname === route.path;
  }

  return pathname === route.path || pathname.startsWith(`${route.path}/`);
}

/**
 * Resolve the most specific registered Portal route for a pathname.
 */
export function portalRouteForPathname(pathname: string): PortalRoute | null {
  return (
    [...portalRoutes]
      .sort((left, right) => right.path.length - left.path.length)
      .find((route) => portalRouteMatchesPathname(route, pathname)) ?? null
  );
}

function navigationSectionsFromRoutes(
  routes: readonly PortalRoute[]
): readonly PortalNavigationSection[] {
  return Object.values(PORTAL_ROUTE_SECTIONS)
    .map((sectionLabel) => ({
      label: sectionLabel,
      items: routes.filter((route) => route.section === sectionLabel)
    }))
    .filter((section) => section.items.length > 0);
}

/**
 * Navigation is a projection of the canonical route model.
 */
export const portalNavigationSections: readonly PortalNavigationSection[] =
  navigationSectionsFromRoutes(portalRoutes);

export function visiblePortalNavigationSections(
  authorization: AtlasEffectivePermissionPatterns
): readonly PortalNavigationSection[] {
  return navigationSectionsFromRoutes(
    portalRoutes.filter((route) => hasAtlasPermission(authorization, route.permission))
  );
}

export function portalPageTitle(pathname: string): string {
  return portalRouteForPathname(pathname)?.label ?? "Portal";
}
