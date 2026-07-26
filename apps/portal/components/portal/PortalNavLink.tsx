"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { PortalNavigationItem } from "../../lib/navigation/portal";

type PortalNavLinkProps = Readonly<{
  item: PortalNavigationItem;
  onNavigate?: () => void;
}>;

export function PortalNavLink({ item, onNavigate }: PortalNavLinkProps): React.ReactElement {
  const pathname = usePathname();

  const isActive =
    item.href === "/portal"
      ? pathname === item.href
      : pathname === item.href || pathname.startsWith(`${item.href}/`);

  return (
    <Link
      aria-current={isActive ? "page" : undefined}
      className="portal-nav-link"
      data-active={isActive ? "true" : "false"}
      href={item.href}
      onClick={onNavigate}
    >
      <span aria-hidden="true" className="portal-nav-abbreviation">
        {item.abbreviation}
      </span>

      <span className="portal-nav-copy">
        <span className="portal-nav-label">{item.label}</span>
        <span className="portal-nav-description">{item.description}</span>
      </span>
    </Link>
  );
}
