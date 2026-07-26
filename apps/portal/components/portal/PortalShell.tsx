"use client";

import { useEffect, useState, type ReactNode } from "react";

import { PortalSidebar } from "./PortalSidebar";
import { PortalTopbar } from "./PortalTopbar";

type PortalShellProps = Readonly<{
  children: ReactNode;
}>;

export function PortalShell({ children }: PortalShellProps): React.ReactElement {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);

  useEffect(() => {
    if (!isNavigationOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        setIsNavigationOpen(false);
      }
    }

    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isNavigationOpen]);

  return (
    <div className="portal-shell">
      <PortalSidebar isOpen={isNavigationOpen} onClose={() => setIsNavigationOpen(false)} />

      <div className="portal-workspace">
        <PortalTopbar onOpenNavigation={() => setIsNavigationOpen(true)} />

        <main className="portal-content" id="portal-main-content">
          {children}
        </main>

        <footer className="portal-footer">
          <span>Project Atlas</span>
          <span>Reliable media infrastructure for friends and family.</span>
        </footer>
      </div>
    </div>
  );
}
