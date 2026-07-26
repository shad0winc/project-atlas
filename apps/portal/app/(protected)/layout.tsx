import type { ReactNode } from "react";

import { RequireAuth } from "../../components/auth/RequireAuth";
import { PortalShell } from "../../components/portal/PortalShell";

type ProtectedLayoutProps = Readonly<{
  children: ReactNode;
}>;

export default function ProtectedLayout({ children }: ProtectedLayoutProps): React.ReactElement {
  return (
    <RequireAuth>
      <PortalShell>{children}</PortalShell>
    </RequireAuth>
  );
}
