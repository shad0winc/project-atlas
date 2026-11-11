"use client";

import { PortalPage } from "../../../components/portal/PortalPage";
import { PortalHome } from "../../../features/home/components/PortalHome";
import { useAuth } from "../../../lib/auth/use-auth";
import { PORTAL_ROUTES } from "../../../lib/navigation/portal";

export default function PortalPageRoute(): React.ReactElement {
  const { user } = useAuth();

  return (
    <PortalPage
      permission={PORTAL_ROUTES.home.permission}
      title="Home"
      description="Pick up where you left off and see what you follow."
    >
      {user && <PortalHome key={user.user_id} userId={user.user_id} />}
    </PortalPage>
  );
}
