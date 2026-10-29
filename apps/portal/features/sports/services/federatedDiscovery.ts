import type { SportsSearchResult, SportsSearchType } from "../types/sports";

export class SportsDiscoveryRateLimitError extends Error {
  constructor() {
    super("Sports search is temporarily rate limited. Please try again shortly.");
    this.name = "SportsDiscoveryRateLimitError";
  }
}

export type SportsDiscoveryProvider = Readonly<{ provider: "thesportsdb" | "espn"; enabled: boolean }>;
export type SportsDiscoverySource = Readonly<{ provider: string; outcome: "pending" | "available" | "unavailable"; reason?: "rate-limit" }>;
export type SportsDiscoverySnapshot = Readonly<{
  results: readonly SportsSearchResult[];
  sources: readonly SportsDiscoverySource[];
  state: "loading" | "complete" | "partial" | "unavailable";
}>;

export function parseDiscoveryProviders(value: unknown): readonly SportsDiscoveryProvider[] {
  if (typeof value !== "object" || value === null || !("version" in value) || value.version !== 1 || !("providers" in value) || !Array.isArray(value.providers) || value.providers.length !== 2) {
    throw new Error("Sports discovery configuration is unavailable.");
  }
  const providers = value.providers.map((row: unknown): SportsDiscoveryProvider => {
    if (typeof row !== "object" || row === null || !("provider" in row) || !("enabled" in row) || (row.provider !== "espn" && row.provider !== "thesportsdb") || typeof row.enabled !== "boolean") {
      throw new Error("Sports discovery configuration is unavailable.");
    }
    return { provider: row.provider, enabled: row.enabled };
  });
  if (new Set(providers.map(row => row.provider)).size !== 2) throw new Error("Sports discovery configuration is unavailable.");
  return providers;
}

function bounded<T>(task: (signal: AbortSignal) => Promise<T>, signal: AbortSignal, timeoutMs: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const controller = new AbortController();
    let done = false;
    const finish = (action: () => void) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      signal.removeEventListener("abort", aborted);
      action();
    };
    const aborted = () => finish(() => { controller.abort(); reject(new Error("Sports search cancelled.")); });
    const timer = setTimeout(() => finish(() => { controller.abort(); reject(new Error("Sports search timed out.")); }), timeoutMs);
    signal.addEventListener("abort", aborted, { once: true });
    if (signal.aborted) { aborted(); return; }
    Promise.resolve().then(() => {
      if (controller.signal.aborted) throw new Error("Sports search cancelled.");
      return task(controller.signal);
    }).then(
      value => finish(() => resolve(value)),
      error => finish(() => reject(error instanceof SportsDiscoveryRateLimitError
        ? error : new Error("Sports source is unavailable."))),
    );
  });
}

export async function searchFederatedSports({ type, query, signal, loadProviders, search, publish, timeoutMs = 10_000 }: Readonly<{
  type: SportsSearchType;
  query: string;
  signal: AbortSignal;
  loadProviders: (signal: AbortSignal) => Promise<readonly SportsDiscoveryProvider[]>;
  search: (type: SportsSearchType, query: string, options: Readonly<{ provider: string; signal: AbortSignal }>) => Promise<readonly SportsSearchResult[]>;
  publish: (snapshot: SportsDiscoverySnapshot) => void;
  timeoutMs?: number;
}>): Promise<void> {
  if (!Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) throw new Error("Invalid Sports search deadline.");
  const normalized = query.trim();
  if (signal.aborted) return;
  if (!normalized) { publish({ results: [], sources: [], state: "complete" }); return; }
  publish({ results: [], sources: [], state: "loading" });
  let providers: readonly SportsDiscoveryProvider[];
  try {
    providers = await bounded(loadProviders, signal, timeoutMs);
  } catch {
    if (!signal.aborted) publish({ results: [], sources: [], state: "unavailable" });
    return;
  }
  if (signal.aborted) return;
  const active = providers.filter(row => row.enabled);
  if (active.length === 0) { publish({ results: [], sources: [], state: "unavailable" }); return; }
  const outcomes = new Map(active.map(row => [row.provider, "pending" as SportsDiscoverySource["outcome"]]));
  const found = new Map<string, readonly SportsSearchResult[]>();
  const rateLimited = new Set<string>();
  const emit = () => {
    if (signal.aborted) return;
    const sources = active.map(row => ({ provider: row.provider, outcome: outcomes.get(row.provider)!,
      ...(rateLimited.has(row.provider) ? { reason: "rate-limit" as const } : {}) }));
    const pending = sources.some(row => row.outcome === "pending");
    const failed = sources.some(row => row.outcome === "unavailable");
    const available = sources.some(row => row.outcome === "available");
    publish({ results: active.flatMap(row => found.get(row.provider) ?? []), sources,
      state: pending ? "loading" : failed ? (available ? "partial" : "unavailable") : "complete" });
  };
  emit();
  await Promise.all(active.map(async source => {
    try {
      const rows = await bounded(child => search(type, normalized, { provider: source.provider, signal: child }), signal, timeoutMs);
      const unique = new Map<string, SportsSearchResult>();
      for (const row of rows) {
        if (row.kind !== type || (row.provider !== undefined && row.provider !== source.provider)) throw new Error("Sports result identity mismatch.");
        const result = { ...row, provider: source.provider };
        const key = JSON.stringify([result.provider, result.kind, result.id]);
        const previous = unique.get(key);
        if (previous && JSON.stringify(previous) !== JSON.stringify(result)) throw new Error("Conflicting Sports identity.");
        unique.set(key, result);
      }
      found.set(source.provider, [...unique.values()]);
      outcomes.set(source.provider, "available");
    } catch (error) {
      if (error instanceof SportsDiscoveryRateLimitError) rateLimited.add(source.provider);
      outcomes.set(source.provider, "unavailable");
    }
    emit();
  }));
}
