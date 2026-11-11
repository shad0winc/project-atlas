import { PortalPage } from "../../../../../components/portal/PortalPage";
import { PortalDashboardView } from "../../../../../features/portal-dashboard/components/PortalDashboardView";
import { PORTAL_ROUTES } from "../../../../../lib/navigation/portal";

export default function AdminDashboard(): React.ReactElement {
  const route = PORTAL_ROUTES.dashboard;

  return (
    <PortalPage
      permission={route.permission}
      title={route.label}
      description={route.pageDescription}
      accessDeniedDescription="Your Atlas account does not have permission to view the system dashboard."
    >
      <PortalDashboardView />
    </PortalPage>
  );
}
