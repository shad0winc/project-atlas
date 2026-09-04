import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type AdminLiveSession = Readonly<{
  sessionId: string;
  targetId: string;
  ageSeconds: number;
  heartbeatAgeSeconds: number;
}>;

export type AdminLiveSessionUser = Readonly<{
  userId: string;
  username: string;
  displayName: string;
  overrideLimit: number | null;
  effectiveLimit: number;
  activeCount: number;
  sessions: readonly AdminLiveSession[];
}>;

export type AdminLiveSessionPolicy = Readonly<{
  version: number;
  defaultLimit: number;
  ttlSeconds: number;
  users: readonly AdminLiveSessionUser[];
}>;

type SessionTransport = Readonly<{
  session_id: string;
  target_id: string;
  age_seconds: number;
  heartbeat_age_seconds: number;
}>;

type UserTransport = Readonly<{
  user_id: string;
  username: string;
  display_name: string;
  override_limit: number | null;
  effective_limit: number;
  active_count: number;
  sessions: readonly SessionTransport[];
}>;

type PolicyTransport = Readonly<{
  version: number;
  default_limit: number;
  ttl_seconds: number;
  users: readonly UserTransport[];
}>;

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} is missing from the Atlas API response.`);
  }
  return value.trim();
}

function positiveInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) {
    throw new Error(`${label} must be a positive integer.`);
  }
  return value;
}

function nonNegativeInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error(`${label} must be a non-negative integer.`);
  }
  return value;
}

function mapSession(session: SessionTransport): AdminLiveSession {
  return {
    sessionId: requiredString(session.session_id, "session id"),
    targetId: requiredString(session.target_id, "session target id"),
    ageSeconds: nonNegativeInteger(session.age_seconds, "session age"),
    heartbeatAgeSeconds: nonNegativeInteger(
      session.heartbeat_age_seconds,
      "session heartbeat age"
    )
  };
}

function mapUser(user: UserTransport): AdminLiveSessionUser {
  return {
    userId: requiredString(user.user_id, "user id"),
    username: requiredString(user.username, "username"),
    displayName: requiredString(user.display_name, "display name"),
    overrideLimit:
      user.override_limit === null
        ? null
        : positiveInteger(user.override_limit, "user override limit"),
    effectiveLimit: positiveInteger(user.effective_limit, "effective limit"),
    activeCount: nonNegativeInteger(user.active_count, "active count"),
    sessions: user.sessions.map(mapSession)
  };
}

function mutationOptions(body?: Readonly<Record<string, unknown>>) {
  return {
    cache: "no-store" as const,
    ...(body === undefined ? {} : { body }),
    retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5_000 }
  };
}

export async function loadAdminLiveSessionPolicy(
  signal?: AbortSignal
): Promise<AdminLiveSessionPolicy> {
  const response = await authenticatedAtlasApiRequest<PolicyTransport>(
    "/admin/live-sessions",
    { method: "GET", cache: "no-store", signal }
  );
  return {
    version: positiveInteger(response.version, "policy version"),
    defaultLimit: positiveInteger(response.default_limit, "default limit"),
    ttlSeconds: positiveInteger(response.ttl_seconds, "session TTL"),
    users: response.users.map(mapUser)
  };
}

export async function updateAdminLiveSessionDefault(limit: number): Promise<void> {
  await authenticatedAtlasApiRequest<unknown>("/admin/live-sessions/default", {
    method: "PATCH",
    ...mutationOptions({ limit: positiveInteger(limit, "default limit") })
  });
}

export async function setAdminLiveSessionUserOverride(
  userId: string,
  limit: number
): Promise<void> {
  await authenticatedAtlasApiRequest<unknown>(
    `/admin/live-sessions/users/${encodeURIComponent(requiredString(userId, "user id"))}`,
    {
      method: "PUT",
      ...mutationOptions({ limit: positiveInteger(limit, "user override limit") })
    }
  );
}

export async function clearAdminLiveSessionUserOverride(userId: string): Promise<void> {
  await authenticatedAtlasApiRequest<unknown>(
    `/admin/live-sessions/users/${encodeURIComponent(requiredString(userId, "user id"))}`,
    { method: "DELETE", ...mutationOptions() }
  );
}
