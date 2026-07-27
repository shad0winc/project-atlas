"use client";

import { useAuth } from "../auth/use-auth";

import {
  hasAnyAtlasPermission,
  hasAtlasPermission,
  hasEveryAtlasPermission,
  type AtlasPermission
} from "./permissions";

export type AtlasPermissionEvaluation = Readonly<{
  roles: readonly string[];
  can: (permission: AtlasPermission) => boolean;
  canAny: (permissions: readonly AtlasPermission[]) => boolean;
  canEvery: (permissions: readonly AtlasPermission[]) => boolean;
}>;

/**
 * Evaluate presentation-layer permissions for the authenticated Portal user.
 *
 * The API remains authoritative. This hook determines only which Portal
 * controls and navigation entries should be presented to the user.
 */
export function usePermission(): AtlasPermissionEvaluation {
  const { user } = useAuth();
  const roles = user?.roles ?? [];

  return {
    roles,
    can: (permission) => hasAtlasPermission(roles, permission),
    canAny: (permissions) => hasAnyAtlasPermission(roles, permissions),
    canEvery: (permissions) => hasEveryAtlasPermission(roles, permissions)
  };
}
