"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "../../lib/auth/use-auth";
import { portalPageTitle } from "../../lib/navigation/portal";

type PortalTopbarProps = Readonly<{
  onOpenNavigation: () => void;
}>;

function userInitials(displayName: string | undefined, username: string | undefined): string {
  const source = displayName?.trim() || username?.trim() || "Atlas User";

  const initials = source
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

  return initials || "AU";
}

export function PortalTopbar({ onOpenNavigation }: PortalTopbarProps): React.ReactElement {
  const pathname = usePathname();
  const router = useRouter();
  const { logout, user } = useAuth();

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const displayName = user?.display_name.trim() || user?.username.trim() || "Atlas user";

  async function handleLogout(): Promise<void> {
    if (isLoggingOut) {
      return;
    }

    setIsLoggingOut(true);

    try {
      await Promise.resolve(logout());
      router.replace("/login");
      router.refresh();
    } finally {
      setIsLoggingOut(false);
      setIsMenuOpen(false);
    }
  }

  return (
    <header className="portal-topbar">
      <div className="portal-topbar-heading">
        <button
          aria-label="Open navigation"
          className="portal-menu-button"
          onClick={onOpenNavigation}
          type="button"
        >
          <span aria-hidden="true">☰</span>
        </button>

        <div>
          <p className="portal-topbar-eyebrow">Project Atlas</p>
          <h1 className="portal-topbar-title">{portalPageTitle(pathname)}</h1>
        </div>
      </div>

      <div className="portal-user-menu">
        <button
          aria-expanded={isMenuOpen}
          aria-haspopup="menu"
          className="portal-user-trigger"
          onClick={() => setIsMenuOpen((current) => !current)}
          type="button"
        >
          <span aria-hidden="true" className="portal-user-avatar">
            {userInitials(user?.display_name, user?.username)}
          </span>

          <span className="portal-user-copy">
            <span className="portal-user-name">{displayName}</span>
            <span className="portal-user-role">
              {user?.roles.length ? user.roles.join(", ") : "Atlas member"}
            </span>
          </span>

          <span aria-hidden="true">⌄</span>
        </button>

        {isMenuOpen ? (
          <div aria-label="User menu" className="portal-user-dropdown" role="menu">
            <div className="portal-user-dropdown-summary">
              <strong>{displayName}</strong>
              <span>{user?.username ?? "Authenticated user"}</span>
            </div>

            <button
              className="portal-user-action"
              disabled={isLoggingOut}
              onClick={handleLogout}
              role="menuitem"
              type="button"
            >
              {isLoggingOut ? "Signing out…" : "Sign out"}
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
