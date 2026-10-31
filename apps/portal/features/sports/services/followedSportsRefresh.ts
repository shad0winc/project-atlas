import type { SportsEvent, SportsFollow } from "../types/sports";
import type { SportsEventFilter, SportsRequestOptions } from "./sports";

export function startFollowedSportsRefresh({
  follows,
  load,
  publish,
  browse,
  intervalMs = 60_000,
  onRefreshing,
  cooldowns = new Map<string, number>(),
}: Readonly<{
  follows: readonly SportsFollow[];
  browse?: Readonly<{ provider: string; type: "team" | "league"; providerId: string }>;
  load: (
    options: SportsRequestOptions,
    filter: SportsEventFilter,
  ) => Promise<readonly SportsEvent[]>;
  publish: (
    providers: readonly string[],
    results: readonly PromiseSettledResult<readonly SportsEvent[]>[] | null,
  ) => void;
  intervalMs?: number;
  onRefreshing?: (refreshing: boolean) => void;
  cooldowns?: Map<string, number>;
}>): () => void {
  const groups = new Map<
    string,
    { eventIds: string[]; teamIds: string[]; leagueIds: string[] }
  >();
  for (const follow of follows) {
    if (!follow.enabled || follow.type === "channel") continue;
    const group = groups.get(follow.provider) ?? {
      eventIds: [],
      teamIds: [],
      leagueIds: [],
    };
    const ids =
      follow.type === "event"
        ? group.eventIds
        : follow.type === "team"
          ? group.teamIds
          : group.leagueIds;
    if (!ids.includes(follow.providerId)) ids.push(follow.providerId);
    groups.set(follow.provider, group);
  }
  // A deliberate browse stays in the refreshed schedule without saving a follow.
  if (browse) {
    const group = groups.get(browse.provider) ?? {
      eventIds: [],
      teamIds: [],
      leagueIds: [],
    };
    const ids = browse.type === "team" ? group.teamIds : group.leagueIds;
    if (!ids.includes(browse.providerId)) ids.push(browse.providerId);
    groups.set(browse.provider, group);
  }
  const providers = [...groups.keys()];
  let stopped = false;
  let controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let expiryTimer: ReturnType<typeof setTimeout> | null = null;
  let nextAllowedAt = 0;
  let failures = 0;
  const minimumDelay = Math.max(1000, intervalMs);
  const clearTimers = () => {
    if (timer !== null) clearTimeout(timer);
    if (expiryTimer !== null) clearTimeout(expiryTimer);
    timer = null;
    expiryTimer = null;
  };
  function queue(): void {
    if (!stopped && providers.length > 0 && document.visibilityState !== "hidden") {
      timer = setTimeout(() => { void refresh(); }, Math.max(1, nextAllowedAt - Date.now()));
    }
  }
  async function refresh(): Promise<void> {
    if (stopped || controller !== null || document.visibilityState === "hidden") return;
    nextAllowedAt = Math.max(nextAllowedAt, ...providers.map(provider => cooldowns.get(provider) ?? 0));
    if (Date.now() < nextAllowedAt) { queue(); return; }
    clearTimers();
    controller = new AbortController();
    const active = controller;
    publish(providers, null);
    if (providers.length === 0) { controller = null; onRefreshing?.(false); publish(providers, []); return; }
    onRefreshing?.(true);
    const results = await Promise.allSettled(
      providers.map(provider => load({ signal: active.signal }, { provider, ...groups.get(provider)! })),
    );
    if (stopped || active.signal.aborted) return;
    controller = null;
    onRefreshing?.(false);
    publish(providers, results);
    const rejected = results.filter(result => result.status === "rejected");
    failures = rejected.length ? failures + 1 : 0;
    const hints = rejected.map(result => {
      const reason: unknown = result.reason;
      if (typeof reason !== "object" || reason === null || !("retryAfterSeconds" in reason)) return 0;
      const seconds = reason.retryAfterSeconds;
      return typeof seconds === "number" && Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : 0;
    });
    // Retry-After is a floor. Failed refreshes back off without hiding the last schedule.
    nextAllowedAt = Date.now() + Math.max(minimumDelay,
      failures ? Math.min(300_000, minimumDelay * 2 ** Math.min(failures - 1, 8)) : 0, ...hints);
    if (rejected.length) providers.forEach(provider => cooldowns.set(provider, nextAllowedAt));
    const now = Date.now();
    const expiries = results.flatMap(result => result.status === "fulfilled"
      ? result.value.map(event => Date.parse(event.metadataExpiresAt ?? "") - now)
        .filter(delay => Number.isFinite(delay) && delay > 0)
      : []);
    // Metadata expiry invalidates the live projection only; it does not spend another provider request.
    if (expiries.length) expiryTimer = setTimeout(() => {
      expiryTimer = null;
      if (!stopped) publish(providers, null);
    }, Math.min(...expiries));
    queue();
  }
  function visibilityChanged(): void {
    clearTimers();
    if (document.visibilityState === "hidden") {
      controller?.abort();
      controller = null;
      onRefreshing?.(false);
      publish(providers, null);
    } else { void refresh(); }
  }
  document.addEventListener("visibilitychange", visibilityChanged);
  void refresh();
  return () => {
    stopped = true;
    controller?.abort();
    clearTimers();
    document.removeEventListener("visibilitychange", visibilityChanged);
  };
}
