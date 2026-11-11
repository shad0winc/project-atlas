"use client";

import Link from "next/link";

import { MediaLibraryContent } from "../library/LibraryPageClient";
import { PortalPage } from "../../../../components/portal/PortalPage";
import { MediaDiscoveryView } from "../../../../features/media";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const mediaRoute = PORTAL_ROUTES.media;

export function MediaPageClient({ library }: { library: boolean }): React.ReactElement {
  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to browse media."
      description={
        mediaRoute.pageDescription ??
        "Browse and search movies and TV shows available through Atlas."
      }
      permission={mediaRoute.permission}
      title={mediaRoute.label}
    >
      <nav aria-label="Media views" className="portal-view-links">
        <Link aria-current={library ? undefined : "page"} href={mediaRoute.path}>Browse</Link>
        <Link aria-current={library ? "page" : undefined} href={`${mediaRoute.path}?view=library`}>Library</Link>
      </nav>
      {library ? <MediaLibraryContent /> : <MediaDiscoveryView />}
    </PortalPage>
  );
}
