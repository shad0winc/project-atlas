"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "../../lib/auth/use-auth";

type RequireAuthProps = Readonly<{
  children: ReactNode;
}>;

export function RequireAuth({ children }: RequireAuthProps): React.ReactElement | null {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, status } = useAuth();

  useEffect(() => {
    if (status !== "unauthenticated") {
      return;
    }

    const nextPath = pathname && pathname.startsWith("/") ? pathname : "/portal";

    router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
  }, [pathname, router, status]);

  if (status === "loading") {
    return (
      <main aria-busy="true" aria-live="polite" className="auth-page">
        <section className="auth-panel">
          <p className="auth-eyebrow">Project Atlas</p>
          <h1 className="auth-title">Loading your session</h1>
          <p className="auth-description">Confirming access to the private Portal.</p>
        </section>
      </main>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
