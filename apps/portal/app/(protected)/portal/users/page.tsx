"use client";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { AdminIdentityView } from "../../../../features/admin-identity";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const usersRoute = PORTAL_ROUTES.users;

export default function UsersPage(): React.ReactElement {
  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to inspect users and invitations."
      description={
        usersRoute.pageDescription ??
        "Manage Atlas user access and invitations through the supported Administrator workflow."
      }
      eyebrow={usersRoute.label}
      permission={usersRoute.permission}
      title="Users"
    >
      <AdminIdentityView />
    </PortalPage>
  );
}
