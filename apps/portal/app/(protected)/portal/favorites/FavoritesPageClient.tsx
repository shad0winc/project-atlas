"use client";

import { useCallback, useState } from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { FavoritesRefreshButton, FavoritesView } from "../../../../features/favorites";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const favoritesRoute = PORTAL_ROUTES.favorites;

export function FavoritesPageClient(): React.ReactElement {
  const [refresh, setRefresh] = useState<() => void>(() => () => undefined);
  const [isBusy, setIsBusy] = useState(true);

  const handleRefreshStateChange = useCallback(
    (nextRefresh: () => void, nextIsBusy: boolean): void => {
      setRefresh(() => nextRefresh);
      setIsBusy(nextIsBusy);
    },
    []
  );

  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to view favorites."
      actions={<FavoritesRefreshButton disabled={isBusy} onRefresh={refresh} />}
      description={
        favoritesRoute.pageDescription ??
        "Review the media currently saved to your personal Favorites list."
      }
      eyebrow={favoritesRoute.label}
      permission={favoritesRoute.permission}
      title="Your favorites"
    >
      <FavoritesView onRefreshStateChange={handleRefreshStateChange} />
    </PortalPage>
  );
}
