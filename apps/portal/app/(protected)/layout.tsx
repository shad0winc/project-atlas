import type { ReactNode } from "react";

import { RequireAuth } from "../../components/auth/RequireAuth";

type ProtectedLayoutProps = Readonly<{
  children: ReactNode;
}>;

export default function ProtectedLayout({ children }: ProtectedLayoutProps): React.ReactElement {
  return <RequireAuth>{children}</RequireAuth>;
}
