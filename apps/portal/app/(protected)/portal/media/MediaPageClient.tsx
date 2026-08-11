"use client";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { MediaDiscoveryView } from "../../../../features/media";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const mediaRoute = PORTAL_ROUTES.media;

export function MediaPageClient(): React.ReactElement {
  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to browse media."
      description={
        mediaRoute.pageDescription ??
        "Browse and search movies and TV shows available through Atlas."
      }
      eyebrow={mediaRoute.label}
      permission={mediaRoute.permission}
      title="Browse media"
    >
      <MediaDiscoveryView />
    </PortalPage>
  );
}
