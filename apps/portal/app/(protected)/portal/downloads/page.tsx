"use client";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { DownloadsView } from "../../../../features/downloads";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const downloadsRoute = PORTAL_ROUTES.downloads;

export default function DownloadsPage(): React.ReactElement {
  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to inspect download activity."
      description={
        downloadsRoute.pageDescription ??
        "Review bounded, read-only download activity reported by the Atlas runtime collector."
      }
      eyebrow={downloadsRoute.label}
      permission={downloadsRoute.permission}
      title="Download activity"
    >
      <DownloadsView />
    </PortalPage>
  );
}
