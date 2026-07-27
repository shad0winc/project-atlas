"use client";

import { RequirePermission } from "../../../components/auth/RequirePermission";
import { DashboardView } from "../../../features/dashboard";
import { useAuth } from "../../../lib/auth/use-auth";
import { ATLAS_PERMISSIONS } from "../../../lib/authorization";

export default function PortalPage(): React.ReactElement {
  const { user } = useAuth();

  const displayName = user?.display_name.trim() || user?.username.trim() || "Atlas user";

  return (
    <RequirePermission
      fallback={
        <div className="portal-page">
          <header className="portal-page-header">
            <div>
              <p className="portal-page-eyebrow">Dashboard</p>

              <h2 className="portal-page-title">Access unavailable</h2>

              <p className="portal-page-description">
                Your Atlas account does not have permission to view the system dashboard.
              </p>
            </div>
          </header>
        </div>
      }
      permission={ATLAS_PERMISSIONS.dashboardRead}
    >
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
    </RequirePermission>
  );
}
