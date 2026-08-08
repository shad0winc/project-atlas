"use client";

import { PortalPage } from "../../../components/portal/PortalPage";
import { PortalDashboardView } from "../../../features/portal-dashboard";
import { useAuth } from "../../../lib/auth/use-auth";
import { PORTAL_ROUTES } from "../../../lib/navigation/portal";

const dashboardRoute = PORTAL_ROUTES.dashboard;

export default function PortalPageRoute(): React.ReactElement {
  const { user } = useAuth();

  const displayName = user?.display_name.trim() || user?.username.trim() || "Atlas user";

  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to view the system dashboard."
      description={dashboardRoute.pageDescription}
      eyebrow={dashboardRoute.label}
      permission={dashboardRoute.permission}
      title={`Welcome back, ${displayName}`}
    >
      <PortalDashboardView />
    </PortalPage>
  );
}
