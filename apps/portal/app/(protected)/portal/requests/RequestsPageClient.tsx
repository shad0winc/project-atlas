"use client";

import { useCallback, useState } from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";

import { RequestsRefreshButton, RequestsView } from "../../../../features/requests";

import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const requestsRoute = PORTAL_ROUTES.requests;

export function RequestsPageClient(): React.ReactElement {
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
      accessDeniedDescription="Your Atlas account does not have permission to view media requests."
      actions={<RequestsRefreshButton disabled={isBusy} onRefresh={refresh} />}
      description={
        requestsRoute.pageDescription ??
        "Review the lifecycle and availability of media requested through Atlas."
      }
      eyebrow={requestsRoute.label}
      permission={requestsRoute.permission}
      title="Your requests"
    >
      <RequestsView onRefreshStateChange={handleRefreshStateChange} />
    </PortalPage>
  );
}
