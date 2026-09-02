"use client";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { SettingsView } from "../../../../features/settings";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const settingsRoute = PORTAL_ROUTES.settings;

export default function SettingsPage(): React.ReactElement {
  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to view personal account settings."
      description={
        settingsRoute.pageDescription ??
        "Review your Atlas account and manage supported personal settings."
      }
      eyebrow={settingsRoute.label}
      permission={settingsRoute.permission}
      title="Settings"
    >
      <SettingsView />
    </PortalPage>
  );
}
