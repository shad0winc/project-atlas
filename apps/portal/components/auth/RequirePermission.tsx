"use client";

import type { ReactNode } from "react";

import { usePermission, type AtlasPermission } from "../../lib/authorization";

type RequirePermissionProps = Readonly<{
  permission: AtlasPermission;
  children: ReactNode;
  fallback?: ReactNode;
}>;

/**
 * Render children only when the authenticated user has the requested
 * presentation-layer permission.
 *
 * This component does not replace API authorization enforcement.
 */
export function RequirePermission({
  permission,
  children,
  fallback = null
}: RequirePermissionProps): React.ReactElement {
  const { can } = usePermission();

  return <>{can(permission) ? children : fallback}</>;
}
