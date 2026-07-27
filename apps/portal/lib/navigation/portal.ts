import {
  ATLAS_PERMISSIONS,
  hasAtlasPermission,
  type AtlasPermission
} from "../authorization/permissions";

export type PortalNavigationItem = Readonly<{
  href: string;
  label: string;
  description: string;
  abbreviation: string;
  permission: AtlasPermission;
}>;

export type PortalNavigationSection = Readonly<{
  label: string;
  items: readonly PortalNavigationItem[];
}>;

export const portalNavigationSections: readonly PortalNavigationSection[] = [
  {
    label: "Workspace",
    items: [
      {
        href: "/portal",
        label: "Dashboard",
        description: "Atlas system overview",
        abbreviation: "DB",
        permission: ATLAS_PERMISSIONS.dashboardRead
      },
      {
        href: "/portal/media",
        label: "Media",
        description: "Libraries and media statistics",
        abbreviation: "ME",
        permission: ATLAS_PERMISSIONS.mediaRead
      },
      {
        href: "/portal/requests",
        label: "Requests",
        description: "Media requests and approvals",
        abbreviation: "RQ",
        permission: ATLAS_PERMISSIONS.requestsRead
      },
      {
        href: "/portal/downloads",
        label: "Downloads",
        description: "Download activity and status",
        abbreviation: "DL",
        permission: ATLAS_PERMISSIONS.monitoringRead
      }
    ]
  },
  {
    label: "Management",
    items: [
      {
        href: "/portal/users",
        label: "Users",
        description: "Accounts and access",
        abbreviation: "US",
        permission: ATLAS_PERMISSIONS.usersRead
      },
      {
        href: "/portal/administration",
        label: "Administration",
        description: "Services and configuration",
        abbreviation: "AD",
        permission: ATLAS_PERMISSIONS.systemHealthRead
      },
      {
        href: "/portal/settings",
        label: "Settings",
        description: "Portal preferences",
        abbreviation: "ST",
        permission: ATLAS_PERMISSIONS.usersSelfRead
      }
    ]
  }
];

export function visiblePortalNavigationSections(
  roles: readonly string[]
): readonly PortalNavigationSection[] {
  return portalNavigationSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => hasAtlasPermission(roles, item.permission))
    }))
    .filter((section) => section.items.length > 0);
}

export function portalPageTitle(pathname: string): string {
  const matchingItem = portalNavigationSections
    .flatMap((section) => section.items)
    .find((item) => {
      if (item.href === "/portal") {
        return pathname === item.href;
      }

      return pathname === item.href || pathname.startsWith(`${item.href}/`);
    });

  return matchingItem?.label ?? "Portal";
}
