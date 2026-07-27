"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { portalRouteMatchesPathname, type PortalRoute } from "../../lib/navigation/portal";

type PortalNavLinkProps = Readonly<{
  item: PortalRoute;
  onNavigate?: () => void;
}>;

export function PortalNavLink({ item, onNavigate }: PortalNavLinkProps): React.ReactElement {
  const pathname = usePathname();
  const isActive = portalRouteMatchesPathname(item, pathname);

  return (
    <Link
      aria-current={isActive ? "page" : undefined}
      className="portal-nav-link"
      data-active={isActive ? "true" : "false"}
      href={item.path}
      onClick={onNavigate}
    >
      <span aria-hidden="true" className="portal-nav-abbreviation">
        {item.abbreviation}
      </span>

      <span className="portal-nav-copy">
        <span className="portal-nav-label">{item.label}</span>
        <span className="portal-nav-description">{item.navigationDescription}</span>
      </span>
    </Link>
  );
}
