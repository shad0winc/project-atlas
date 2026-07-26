export type PortalNavigationItem = Readonly<{
  href: string;
  label: string;
  description: string;
  abbreviation: string;
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
        abbreviation: "DB"
      },
      {
        href: "/portal/media",
        label: "Media",
        description: "Libraries and media statistics",
        abbreviation: "ME"
      },
      {
        href: "/portal/requests",
        label: "Requests",
        description: "Media requests and approvals",
        abbreviation: "RQ"
      },
      {
        href: "/portal/downloads",
        label: "Downloads",
        description: "Download activity and status",
        abbreviation: "DL"
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
        abbreviation: "US"
      },
      {
        href: "/portal/administration",
        label: "Administration",
        description: "Services and configuration",
        abbreviation: "AD"
      },
      {
        href: "/portal/settings",
        label: "Settings",
        description: "Portal preferences",
        abbreviation: "ST"
      }
    ]
  }
];

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
