"use client";

import Link from "next/link";

import { useAuth } from "../../lib/auth/use-auth";
import { visiblePortalNavigationSections } from "../../lib/navigation/portal";

import { PortalNavLink } from "./PortalNavLink";

type PortalSidebarProps = Readonly<{
  isOpen: boolean;
  onClose: () => void;
}>;

export function PortalSidebar({ isOpen, onClose }: PortalSidebarProps): React.ReactElement {
  const { user } = useAuth();
  const navigationSections = visiblePortalNavigationSections({
    grantedPermissionPatterns: user?.granted_permission_patterns ?? [],
    deniedPermissionPatterns: user?.denied_permission_patterns ?? []
  });

  return (
    <>
      <button
        aria-label="Close navigation"
        className="portal-sidebar-backdrop"
        data-open={isOpen ? "true" : "false"}
        onClick={onClose}
        type="button"
      />

      <aside
        aria-label="Portal navigation"
        className="portal-sidebar"
        data-open={isOpen ? "true" : "false"}
      >
        <div className="portal-sidebar-header">
          <Link className="portal-sidebar-brand" href="/portal" onClick={onClose}>
            <span aria-hidden="true" className="portal-sidebar-mark">
              A
            </span>

            <span>
              <span className="portal-sidebar-title">Project Atlas</span>
              <span className="portal-sidebar-subtitle">Private Portal</span>
            </span>
          </Link>

          <button
            aria-label="Close navigation"
            className="portal-sidebar-close"
            onClick={onClose}
            type="button"
          >
            ×
          </button>
        </div>

        <nav className="portal-navigation">
          {navigationSections.map((section) => (
            <section className="portal-nav-section" key={section.label}>
              <h2 className="portal-nav-section-title">{section.label}</h2>

              <div className="portal-nav-list">
                {section.items.map((item) => (
                  <PortalNavLink item={item} key={item.path} onNavigate={onClose} />
                ))}
              </div>
            </section>
          ))}
        </nav>

        <div className="portal-sidebar-footer">
          <span className="portal-sidebar-status-dot" />
          <span>Atlas Portal connected</span>
        </div>
      </aside>
    </>
  );
}
