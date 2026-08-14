"use client";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { ServiceView } from "../../../../features/services";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const servicesRoute = PORTAL_ROUTES.services;

export default function ServicesPage(): React.ReactElement {
  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to inspect managed services."
      description={
        servicesRoute.pageDescription ??
        "Review Atlas-managed service health and read-only runtime details."
      }
      eyebrow={servicesRoute.label}
      permission={servicesRoute.permission}
      title="Managed services"
    >
      <ServiceView />
    </PortalPage>
  );
}
