"use client";

import { PortalPage } from "../../../../../components/portal/PortalPage";
import { DownloadManagementView } from "../../../../../features/download-management";
import { PORTAL_ROUTES } from "../../../../../lib/navigation/portal";

const downloadManagementRoute = PORTAL_ROUTES.downloadManagement;

export default function DownloadManagementPage(): React.ReactElement {
  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to manage download jobs."
      description={
        downloadManagementRoute.pageDescription ??
        "Stop or resume seeding and remove download jobs without deleting downloaded media."
      }
      eyebrow={downloadManagementRoute.label}
      permission={downloadManagementRoute.permission}
      title="Download Management"
    >
      <DownloadManagementView />
    </PortalPage>
  );
}
