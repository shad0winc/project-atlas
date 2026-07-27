/**
 * Portal-side representation of the Atlas authorization catalog.
 *
 * This catalog controls presentation and navigation only. The Atlas API
 * remains the authoritative security boundary and independently enforces
 * every protected request.
 */

export const ATLAS_PERMISSIONS = {
  dashboardRead: "atlas.dashboard.read",
  favoritesRead: "favorites.read",
  favoritesWrite: "favorites.write",
  mediaRead: "media.read",
  monitoringRead: "monitoring.read",
  requestsCreate: "requests.create",
  requestsRead: "requests.read",
  systemHealthRead: "system.health.read",
  usersRead: "users.read",
  usersSelfRead: "users.self.read",
  usersSelfUpdate: "users.self.update"
} as const;

export type AtlasPermission =
  (typeof ATLAS_PERMISSIONS)[keyof typeof ATLAS_PERMISSIONS] | (string & {});

export const ATLAS_ROLE_ALIASES: Readonly<Record<string, string>> = Object.freeze({
  admin: "global_admin",
  games_admin: "gameserver_admin",
  readonly: "read_only",
  user: "member"
});

export const ATLAS_ROLE_PERMISSIONS: Readonly<Record<string, readonly string[]>> = Object.freeze({
  owner: Object.freeze(["*"]),

  global_admin: Object.freeze([
    "atlas.*",
    "audit.*",
    "cleanup.*",
    "favorites.*",
    "gameservers.*",
    "media.*",
    "modules.*",
    "monitoring.*",
    "requests.*",
    "retention.*",
    "roles.*",
    "scheduler.*",
    "system.*",
    "users.*"
  ]),

  atlas_admin: Object.freeze([
    "atlas.*",
    "cleanup.*",
    "favorites.*",
    "media.*",
    "modules.read",
    "monitoring.read",
    "requests.*",
    "retention.*",
    "scheduler.*",
    "system.health.read",
    "system.logs.read"
  ]),

  gameserver_admin: Object.freeze([
    "gameservers.*",
    "monitoring.read",
    "system.health.read",
    "system.logs.read"
  ]),

  monitoring_admin: Object.freeze([
    "monitoring.*",
    "system.checks.run",
    "system.health.read",
    "system.logs.read"
  ]),

  operator: Object.freeze([
    "cleanup.run",
    "gameservers.restart",
    "gameservers.start",
    "gameservers.stop",
    "monitoring.read",
    "scheduler.run",
    "system.checks.run",
    "system.health.read",
    "system.logs.read"
  ]),

  check_runner: Object.freeze(["monitoring.read", "system.checks.run", "system.health.read"]),

  read_only: Object.freeze(["*.read"]),

  member: Object.freeze([
    "atlas.dashboard.read",
    "favorites.read",
    "favorites.write",
    "media.read",
    "requests.create",
    "requests.read",
    "users.self.read",
    "users.self.update"
  ])
});

const EMPTY_PERMISSIONS: readonly string[] = Object.freeze([]);

function normalizeRequiredValue(value: string, label: string): string {
  const normalized = value.trim().toLowerCase();

  if (!normalized) {
    throw new Error(`${label} cannot be empty.`);
  }

  return normalized;
}

export function normalizeAtlasRole(role: string): string {
  const normalized = normalizeRequiredValue(role, "Atlas role");
  return ATLAS_ROLE_ALIASES[normalized] ?? normalized;
}

export function normalizeAtlasPermission(permission: string): string {
  return normalizeRequiredValue(permission, "Atlas permission");
}

/**
 * Match an Atlas permission pattern with the same wildcard behavior used by
 * Python fnmatchcase(), which backs the Atlas API authorization service.
 *
 * Atlas currently permits only `*` wildcard patterns:
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

  /*
   * Escape regular-expression syntax while preserving `*`, then translate
   * each `*` into an unrestricted wildcard.
   */
  const escapedPattern = normalizedPattern.replace(/[.+?^${}()|[\]\\]/g, "\\$&");

  const regularExpressionPattern = escapedPattern.replace(/\*/g, ".*");

  return new RegExp(`^${regularExpressionPattern}$`).test(normalizedPermission);
}

export function atlasRolePermissions(role: string): readonly string[] {
  return ATLAS_ROLE_PERMISSIONS[normalizeAtlasRole(role)] ?? EMPTY_PERMISSIONS;
}

export function hasAtlasPermission(roles: readonly string[], requestedPermission: string): boolean {
  const normalizedPermission = normalizeAtlasPermission(requestedPermission);

  return roles.some((role) =>
    atlasRolePermissions(role).some((pattern) =>
      atlasPermissionPatternMatches(pattern, normalizedPermission)
    )
  );
}

export function hasEveryAtlasPermission(
  roles: readonly string[],
  requestedPermissions: readonly string[]
): boolean {
  return requestedPermissions.every((permission) => hasAtlasPermission(roles, permission));
}

export function hasAnyAtlasPermission(
  roles: readonly string[],
  requestedPermissions: readonly string[]
): boolean {
  return requestedPermissions.some((permission) => hasAtlasPermission(roles, permission));
}
