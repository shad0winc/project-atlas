import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";
import { createSportsEventCollection, type SportsEvent, type SportsEventTransport } from "../types/sports";

export type CuratedStatus = "disabled" | "preparing" | "ready" | "partial" | "stale" | "unavailable" | "unsupported";
export type CuratedCompetition = Readonly<{
  id: string; sport: string; name: string; provider: "espn"; providerLeagueId: string | null;
  teamDirectorySupported: boolean; status: "configured" | "disabled" | "unsupported";
}>;
export type CuratedCatalog = Readonly<{ enabled: boolean; competitions: readonly CuratedCompetition[] }>;
export type CuratedTeams = Readonly<{
  competitionId: string; status: CuratedStatus; teams: readonly Readonly<{ id: string; name: string }>[];
}>;
export type CuratedSchedule = Readonly<{
  competitionId: string; providerLeagueId: string; startAt: string; endAt: string;
  evaluatedAt: string; status: CuratedStatus; coverageComplete: boolean;
  observedAt: string | null; expiresAt: string | null; retryAfterSeconds: number;
  events: readonly SportsEvent[]; retained: boolean;
}>;
export type CuratedPeriod = "today" | "tomorrow" | "week";
const routes: Readonly<Record<string, string | null>> = {
  nfl: "football/nfl", "college-football": null, nba: "basketball/nba", "college-basketball": null,
  mlb: "baseball/mlb", nhl: "hockey/nhl", "premier-league": "soccer/eng.1", ufc: "mma/ufc",
};
const statuses: readonly string[] = ["disabled", "preparing", "ready", "partial", "stale", "unavailable", "unsupported"];

function object(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Invalid shared Sports snapshot.");
  return value as Record<string, unknown>;
}
function text(value: unknown, maximum = 512): string {
  if (typeof value !== "string" || !value.trim() || value.length > maximum) throw new Error("Invalid shared Sports text.");
  return value;
}
function stamp(value: unknown): string {
  const result = text(value, 64);
  if (!/(Z|[+-]\d{2}:\d{2})$/.test(result) || !Number.isFinite(Date.parse(result))) throw new Error("Invalid shared Sports timestamp.");
  return result;
}
function header(value: unknown): Record<string, unknown> {
  const row = object(value);
  if (row.version !== 1) throw new Error("Unsupported shared Sports snapshot.");
  stamp(row.evaluated_at);
  return row;
}
function scope(row: Record<string, unknown>, competition: string): string | null {
  if (!(Object.hasOwn(routes, competition)) || row.competition_id !== competition || row.provider !== "espn" || row.provider_league_id !== routes[competition]) {
    throw new Error("Shared Sports competition identity changed.");
  }
  return routes[competition];
}
function status(value: unknown): CuratedStatus {
  if (typeof value !== "string" || !statuses.includes(value)) throw new Error("Invalid shared Sports status.");
  return value as CuratedStatus;
}

export function parseCuratedCatalog(value: unknown): CuratedCatalog {
  const row = header(value);
  if (typeof row.enabled !== "boolean" || !Array.isArray(row.competitions) || row.competitions.length !== 8) throw new Error("Invalid shared Sports catalog.");
  const ids = new Set<string>();
  const competitions = row.competitions.map(value => {
    const item = object(value), id = text(item.id, 64);
    if (!(Object.hasOwn(routes, id)) || ids.has(id) || item.provider !== "espn" || item.provider_league_id !== routes[id]
      || typeof item.team_directory_supported !== "boolean" || !["configured", "disabled", "unsupported"].includes(String(item.status))
      || (item.status === "unsupported") !== (routes[id] === null) || (!row.enabled && item.status === "configured")) throw new Error("Invalid shared Sports competition.");
    ids.add(id);
    return { id, sport: text(item.sport, 64), name: text(item.name, 128), provider: "espn" as const,
      providerLeagueId: routes[id], teamDirectorySupported: item.team_directory_supported,
      status: item.status as CuratedCompetition["status"] };
  });
  return { enabled: row.enabled, competitions };
}

export function parseCuratedTeams(value: unknown, competition: string): CuratedTeams {
  const row = header(value), route = scope(row, competition), state = status(row.status);
  if (!Array.isArray(row.teams) || row.teams.length > 500) throw new Error("Invalid cached team directory.");
  const ids = new Set<string>(), prefix = (route ?? "").replaceAll("/", "-") + "-";
  const teams = row.teams.map(value => {
    const item = object(value), id = text(item.id, 128);
    if (!route || !id.startsWith(prefix) || !/^\d+$/.test(id.slice(prefix.length)) || ids.has(id)) throw new Error("Invalid cached team identity.");
    ids.add(id);
    return { id, name: text(item.name) };
  });
  return { competitionId: competition, status: state, teams };
}

export function parseCuratedSchedule(value: unknown, competition: string, window: Readonly<{ startAt: string; endAt: string }>): CuratedSchedule {
  const row = header(value), route = scope(row, competition), state = status(row.status);
  const startAt = stamp(row.start_at), endAt = stamp(row.end_at);
  if (!route || Date.parse(startAt) !== Date.parse(window.startAt) || Date.parse(endAt) !== Date.parse(window.endAt)
    || !(Date.parse(endAt) > Date.parse(startAt)) || Date.parse(endAt) - Date.parse(startAt) > 604_800_000
    || row.provider_completeness_proven !== false || row.coverage_complete !== (state === "ready")
    || !Number.isInteger(row.required_buckets) || Number(row.required_buckets) < 1 || Number(row.required_buckets) > 9
    || !Number.isInteger(row.fresh_buckets) || Number(row.fresh_buckets) < 0 || Number(row.fresh_buckets) > Number(row.required_buckets)
    || (state === "ready" && row.fresh_buckets !== row.required_buckets)
    || !Number.isInteger(row.retry_after_seconds) || Number(row.retry_after_seconds) < 0 || Number(row.retry_after_seconds) > 3600
    || !Array.isArray(row.events) || row.events.length > 500) throw new Error("Invalid shared schedule coverage.");
  const prefix = route.replaceAll("/", "-") + "-", ids = new Set<string>();
  for (const value of row.events) {
    const event = object(value), id = text(event.provider_event_id, 128);
    if (event.provider !== "espn" || event.provider_league_id !== route || !id.startsWith(prefix)
      || !/^\d+$/.test(id.slice(prefix.length)) || ids.has(id)) throw new Error("Invalid shared event identity.");
    ids.add(id);
    const start = Date.parse(stamp(event.start_at));
    if (start < Date.parse(startAt) || start >= Date.parse(endAt)) throw new Error("Shared event outside selected window.");
  }
  const events = createSportsEventCollection({ events: row.events as SportsEventTransport[] });
  return { competitionId: competition, providerLeagueId: route, startAt, endAt, evaluatedAt: stamp(row.evaluated_at), status: state,
    coverageComplete: row.coverage_complete as boolean, observedAt: row.observed_at === null ? null : stamp(row.observed_at),
    expiresAt: row.expires_at === null ? null : stamp(row.expires_at), retryAfterSeconds: Number(row.retry_after_seconds), events, retained: false };
}

export function curatedWindow(period: CuratedPeriod, now = new Date()): Readonly<{ startAt: string; endAt: string }> {
  if (!Number.isFinite(now.getTime()) || !["today", "tomorrow", "week"].includes(period)) throw new Error("Invalid schedule date window.");
  const start = new Date(now), end = new Date(now);
  if (period === "week") end.setTime(start.getTime() + 604_800_000);
  else {
    start.setHours(0, 0, 0, 0);
    if (period === "tomorrow") start.setDate(start.getDate() + 1);
    end.setTime(start.getTime()); end.setDate(end.getDate() + 1);
  }
  return { startAt: start.toISOString(), endAt: end.toISOString() };
}

export function retainCuratedSchedule(previous: CuratedSchedule | null, incoming: CuratedSchedule): CuratedSchedule {
  if (!previous || previous.competitionId !== incoming.competitionId || incoming.coverageComplete || incoming.events.length > 0
    || !["preparing", "unavailable"].includes(incoming.status) || !previous.observedAt
    || Date.parse(incoming.evaluatedAt) - Date.parse(previous.observedAt) > 86_400_000) return incoming;
  const events = previous.events.filter(event => Date.parse(event.startAt) >= Date.parse(incoming.startAt) && Date.parse(event.startAt) < Date.parse(incoming.endAt));
  return events.length ? { ...incoming, events, observedAt: previous.observedAt, expiresAt: previous.expiresAt, retained: true } : incoming;
}

export function filterCuratedTeam(snapshot: CuratedSchedule | null, teamId: string): readonly SportsEvent[] {
  return snapshot?.events.filter(event => !teamId || event.homeTeamId === teamId || event.awayTeamId === teamId) ?? [];
}

async function cached(path: string, signal?: AbortSignal): Promise<unknown> {
  return authenticatedAtlasApiRequest<unknown>(path, { method: "GET", cache: "no-store", signal,
    retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5000 } });
}
export async function loadCuratedCatalog(signal?: AbortSignal): Promise<CuratedCatalog> {
  return parseCuratedCatalog(await cached("/sports/curated/catalog", signal));
}
export async function loadCuratedTeams(competition: string, signal?: AbortSignal): Promise<CuratedTeams> {
  return parseCuratedTeams(await cached("/sports/curated/teams?" + new URLSearchParams({ competition }), signal), competition);
}
export async function loadCuratedSchedule(competition: string, period: CuratedPeriod, signal?: AbortSignal): Promise<CuratedSchedule> {
  const window = curatedWindow(period);
  return parseCuratedSchedule(await cached("/sports/curated/schedule?" + new URLSearchParams({ competition, start_at: window.startAt, end_at: window.endAt }), signal), competition, window);
}
