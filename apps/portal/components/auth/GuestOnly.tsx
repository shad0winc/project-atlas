"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "../../lib/auth/use-auth";

type GuestOnlyProps = Readonly<{
  children: ReactNode;
}>;

export function GuestOnly({ children }: GuestOnlyProps): React.ReactElement | null {
  const router = useRouter();
  const { isAuthenticated, status } = useAuth();

  useEffect(() => {
    if (status === "authenticated" && isAuthenticated) {
      router.replace("/portal");
    }
  }, [isAuthenticated, router, status]);

  if (status === "authenticated" && isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
