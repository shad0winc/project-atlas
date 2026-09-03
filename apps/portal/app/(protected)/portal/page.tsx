"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { PortalPage } from "../../../components/portal/PortalPage";
import { PortalDashboardView } from "../../../features/portal-dashboard";
import { useAuth } from "../../../lib/auth/use-auth";
import { usePermission } from "../../../lib/authorization/use-permission";
import { PORTAL_ROUTES } from "../../../lib/navigation/portal";

const dashboardRoute = PORTAL_ROUTES.dashboard;
const mediaRoute = PORTAL_ROUTES.media;

export default function PortalPageRoute(): React.ReactElement {
  const router = useRouter();
  const { user } = useAuth();
  const { can } = usePermission();

  const canViewDashboard = can(dashboardRoute.permission);
  const canViewMedia = can(mediaRoute.permission);
  const shouldOpenMedia = !canViewDashboard && canViewMedia;

  useEffect(() => {
    if (shouldOpenMedia) {
      router.replace(mediaRoute.path);
    }
  }, [router, shouldOpenMedia]);

  const displayName =
    user?.display_name.trim() ||
    user?.username.trim() ||
    "Atlas user";

  if (shouldOpenMedia) {
    return (
      <section aria-busy="true">
        <p>Opening Media…</p>
      </section>
    );
  }

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
