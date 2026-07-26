"use client";

import { DashboardView } from "../../../features/dashboard";
import { useAuth } from "../../../lib/auth/use-auth";

export default function PortalPage(): React.ReactElement {
  const { user } = useAuth();

  const displayName = user?.display_name.trim() || user?.username.trim() || "Atlas user";

  return (
    <div className="portal-page">
      <header className="portal-page-header">
        <div>
          <p className="portal-page-eyebrow">Dashboard</p>

          <h2 className="portal-page-title">Welcome back, {displayName}</h2>

          <p className="portal-page-description">
            Review the current state of your Project Atlas environment.
          </p>
        </div>
      </header>

      <DashboardView />
    </div>
  );
}
