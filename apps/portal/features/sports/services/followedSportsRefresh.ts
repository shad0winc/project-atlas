import type { SportsEvent, SportsFollow } from "../types/sports";
import type { SportsEventFilter, SportsRequestOptions } from "./sports";

export function startFollowedSportsRefresh({
  follows,
  load,
  publish,
  intervalMs = 60_000,
}: Readonly<{
  follows: readonly SportsFollow[];
  load: (
    options: SportsRequestOptions,
    filter: SportsEventFilter,
  ) => Promise<readonly SportsEvent[]>;
  publish: (
    providers: readonly string[],
    results: readonly PromiseSettledResult<readonly SportsEvent[]>[] | null,
  ) => void;
  intervalMs?: number;
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
  const providers = [...groups.keys()];
  let stopped = false;
  let controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  async function refresh(): Promise<void> {
    controller?.abort();
    controller = new AbortController();
    const active = controller;
    publish(providers, null);
    if (document.visibilityState !== "hidden") {
      const results = await Promise.allSettled(
        providers.map((provider) =>
          load(
            { signal: active.signal },
            { provider, ...groups.get(provider)! },
          ),
        ),
      );
      if (stopped || active.signal.aborted) return;
      publish(providers, results);
    }
    if (!stopped && providers.length > 0)
      timer = setTimeout(() => {
        void refresh();
      }, intervalMs);
  }
  function visibilityChanged(): void {
    if (timer !== null) clearTimeout(timer);
    void refresh();
  }
  document.addEventListener("visibilitychange", visibilityChanged);
  void refresh();
  return () => {
    stopped = true;
    controller?.abort();
    if (timer !== null) clearTimeout(timer);
    document.removeEventListener("visibilitychange", visibilityChanged);
  };
}
