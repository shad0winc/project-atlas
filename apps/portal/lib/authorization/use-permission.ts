"use client";

import { useAuth } from "../auth/use-auth";

import {
  hasAnyAtlasPermission,
  hasAtlasPermission,
  hasEveryAtlasPermission,
  type AtlasEffectivePermissionPatterns,
  type AtlasPermission
} from "./permissions";

export type AtlasPermissionEvaluation = Readonly<{
  grantedPermissionPatterns: readonly string[];
  deniedPermissionPatterns: readonly string[];
  can: (permission: AtlasPermission) => boolean;
  canAny: (permissions: readonly AtlasPermission[]) => boolean;
  canEvery: (permissions: readonly AtlasPermission[]) => boolean;
}>;

/**
 * Evaluate presentation-layer permissions for the authenticated Portal user.
 *
 * Effective grants and denials are resolved by the Atlas API. This hook only
 * applies those returned patterns to Portal navigation and presentation.
 */
export function usePermission(): AtlasPermissionEvaluation {
  const { user } = useAuth();

  const authorization: AtlasEffectivePermissionPatterns = {
    grantedPermissionPatterns: user?.granted_permission_patterns ?? [],
    deniedPermissionPatterns: user?.denied_permission_patterns ?? []
  };

  return {
    ...authorization,
    can: (permission) => hasAtlasPermission(authorization, permission),
    canAny: (permissions) => hasAnyAtlasPermission(authorization, permissions),
    canEvery: (permissions) => hasEveryAtlasPermission(authorization, permissions)
  };
}
