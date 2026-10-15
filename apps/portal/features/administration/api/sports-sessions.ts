import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type SportsSessionObservation = Readonly<{
  observed_at: string;
  state_sha256: string;
  ttl_seconds: number;
  retained_count: number;
  recent_count: number;
  expired_count: number;
  sessions: readonly Readonly<{
    session_id: string; user_id: string; target_id: string;
    age_seconds: number; heartbeat_age_seconds: number; heartbeat_expired: boolean;
  }>[];
}>;

function count(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= 256;
}
export async function loadSportsSessionObservation(signal?: AbortSignal): Promise<SportsSessionObservation> {
  const data = await authenticatedAtlasApiRequest<SportsSessionObservation>(
    "/admin/live-sessions/sports", { method: "GET", cache: "no-store", signal },
  );
  if (!data || typeof data.observed_at !== "string" || !Number.isFinite(Date.parse(data.observed_at)) ||
      typeof data.state_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(data.state_sha256) ||
      !count(data.ttl_seconds) || data.ttl_seconds === 0 ||
      !count(data.retained_count) || !count(data.recent_count) || !count(data.expired_count) ||
      !Array.isArray(data.sessions) || data.sessions.length !== data.retained_count ||
      data.recent_count + data.expired_count !== data.retained_count ||
      !data.sessions.every(row => row && identifier(row.session_id) && identifier(row.user_id) &&
        identifier(row.target_id) && count(row.age_seconds) && count(row.heartbeat_age_seconds) &&
        typeof row.heartbeat_expired === "boolean" &&
        row.heartbeat_expired === (row.heartbeat_age_seconds >= data.ttl_seconds)) ||
      new Set(data.sessions.map(row => row.session_id)).size !== data.retained_count ||
      data.sessions.filter(row => row.heartbeat_expired).length !== data.expired_count) {
    throw new Error("Sports session observation is unavailable.");
  }
  return data;
}
