/**
 * Stable permission identifiers and presentation-layer evaluation helpers.
 *
 * The Atlas API owns role resolution, direct grants, explicit denials, and
 * enforcement. The Portal consumes only the effective permission-pattern
 * collections returned in the authenticated-user session contract.
 */

export const ATLAS_PERMISSIONS = {
  dashboardRead: "atlas.dashboard.read",
  favoritesRead: "favorites.read",
  favoritesWrite: "favorites.write",
  mediaRead: "media.read",
  monitoringRead: "monitoring.read",
  downloadsManage: "downloads.manage",
  requestsCancel: "requests.cancel",
  requestsCreate: "requests.create",
  requestsRead: "requests.read",
  sportsEventsRequest: "sports.events.request",
  sportsRead: "sports.read",
  systemHealthRead: "system.health.read",
  usersCreate: "users.create",
  usersRead: "users.read",
  usersUpdate: "users.update",
  rolesAssign: "roles.assign",
  usersSelfRead: "users.self.read",
  usersSelfUpdate: "users.self.update"
} as const;

export type AtlasPermission =
  (typeof ATLAS_PERMISSIONS)[keyof typeof ATLAS_PERMISSIONS] | (string & {});

export type AtlasEffectivePermissionPatterns = Readonly<{
  grantedPermissionPatterns: readonly string[];
  deniedPermissionPatterns: readonly string[];
}>;

function normalizeRequiredValue(value: string, label: string): string {
  const normalized = value.trim().toLowerCase();

  if (!normalized) {
    throw new Error(`${label} cannot be empty.`);
  }

  return normalized;
}

export function normalizeAtlasPermission(permission: string): string {
  return normalizeRequiredValue(permission, "Atlas permission");
}

/**
 * Match an Atlas permission pattern with the same wildcard behavior used by
 * Python fnmatchcase(), which backs the Atlas API authorization service.
 *
 * Atlas currently permits `*` wildcard patterns such as:
 *
 *   *          matches every permission
 *   atlas.*    matches atlas.dashboard.read
 *   users.*    matches users.self.update
 *   *.read     matches atlas.dashboard.read
 */
export function atlasPermissionPatternMatches(
  pattern: string,
  requestedPermission: string
): boolean {
  const normalizedPattern = normalizeAtlasPermission(pattern);
  const normalizedPermission = normalizeAtlasPermission(requestedPermission);

  if (normalizedPattern === "*") {
    return true;
  }

  const escapedPattern = normalizedPattern.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
  const regularExpressionPattern = escapedPattern.replace(/\*/g, ".*");

  return new RegExp(`^${regularExpressionPattern}$`).test(normalizedPermission);
}

function matchesAnyPermissionPattern(patterns: readonly string[], permission: string): boolean {
  return patterns.some((pattern) => atlasPermissionPatternMatches(pattern, permission));
}

/**
 * Evaluate one concrete permission against API-resolved effective patterns.
 *
 * Explicit denials always take precedence over grants, including wildcard
 * grants. This mirrors the Atlas API authorization service.
 */
export function hasAtlasPermission(
  authorization: AtlasEffectivePermissionPatterns,
  requestedPermission: string
): boolean {
  const normalizedPermission = normalizeAtlasPermission(requestedPermission);

  if (matchesAnyPermissionPattern(authorization.deniedPermissionPatterns, normalizedPermission)) {
    return false;
  }

  return matchesAnyPermissionPattern(authorization.grantedPermissionPatterns, normalizedPermission);
}

export function hasEveryAtlasPermission(
  authorization: AtlasEffectivePermissionPatterns,
  requestedPermissions: readonly string[]
): boolean {
  return requestedPermissions.every((permission) => hasAtlasPermission(authorization, permission));
}

export function hasAnyAtlasPermission(
  authorization: AtlasEffectivePermissionPatterns,
  requestedPermissions: readonly string[]
): boolean {
  return requestedPermissions.some((permission) => hasAtlasPermission(authorization, permission));
}
