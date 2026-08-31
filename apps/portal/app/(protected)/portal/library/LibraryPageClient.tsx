"use client";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { MediaCatalogView } from "../../../../features/media";
import { RequestsView } from "../../../../features/requests";
import { ATLAS_PERMISSIONS, usePermission } from "../../../../lib/authorization";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const libraryRoute = PORTAL_ROUTES.library;

export function LibraryPageClient(): React.ReactElement {
  const { can } = usePermission();
  const canReadRequests = can(ATLAS_PERMISSIONS.requestsRead);

  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to view the media library."
      description={
        libraryRoute.pageDescription ??
        "Watch available media and follow the lifecycle of media requested through Atlas."
      }
      eyebrow={libraryRoute.label}
      permission={libraryRoute.permission}
      title="Your library"
    >
      <MediaCatalogView />

      <section aria-labelledby="library-activity-title" className="media-discovery-view">
        <div className="media-discovery-results-header">
          <div>
            <p className="media-discovery-eyebrow">Your activity</p>
            <h2 id="library-activity-title">Request status</h2>
            <p className="media-discovery-overview">
              Follow requested media from submission through availability without managing download jobs.
            </p>
          </div>
        </div>

        {canReadRequests ? (
          <RequestsView />
        ) : (
          <p className="media-discovery-message">
            Your account can browse available media but cannot view request activity.
          </p>
        )}
      </section>
    </PortalPage>
  );
}
