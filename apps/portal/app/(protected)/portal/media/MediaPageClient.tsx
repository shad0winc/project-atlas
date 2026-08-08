"use client";

import { useCallback, useState } from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { MediaRefreshButton, MediaView } from "../../../../features/media";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const mediaRoute = PORTAL_ROUTES.media;

export function MediaPageClient(): React.ReactElement {
  const [refresh, setRefresh] = useState<() => void>(() => () => undefined);
  const [isRefreshing, setIsRefreshing] = useState(true);

  const handleRefreshStateChange = useCallback(
    (nextRefresh: () => void, nextIsRefreshing: boolean): void => {
      setRefresh(() => nextRefresh);
      setIsRefreshing(nextIsRefreshing);
    },
    []
  );

  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to view media library statistics."
      actions={<MediaRefreshButton disabled={isRefreshing} onRefresh={refresh} />}
      description={
        mediaRoute.pageDescription ??
        "Review the libraries and collection statistics currently reported by Atlas."
      }
      eyebrow={mediaRoute.label}
      permission={mediaRoute.permission}
      title="Media libraries"
    >
      <MediaView onRefreshStateChange={handleRefreshStateChange} />
    </PortalPage>
  );
}
