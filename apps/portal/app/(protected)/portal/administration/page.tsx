"use client";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { AdministrationView } from "../../../../features/administration";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const administrationRoute = PORTAL_ROUTES.administration;

export default function AdministrationPage(): React.ReactElement {
  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to access administration."
      description="Open the supported Atlas management surfaces for users, services, requests, media, and sports."
      eyebrow={administrationRoute.label}
      permission={administrationRoute.permission}
      title="Administration"
    >
      <AdministrationView />
    </PortalPage>
  );
}
