import { afterEach, describe, expect, it, vi } from "vitest";
import { parseDiscoveryProviders, searchFederatedSports, type SportsDiscoveryProvider, type SportsDiscoverySnapshot } from "./federatedDiscovery";
import type { SportsSearchResult, SportsSearchType } from "../types/sports";
const providers: readonly SportsDiscoveryProvider[] = [{ provider: "thesportsdb", enabled: true }, { provider: "espn", enabled: true }];
const team = (provider: string): SportsSearchResult => ({ kind: "team", provider, id: "same-id", name: "Rams", sport: "Football", league: "NFL" });
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
afterEach(() => vi.useRealTimers());
function run(search: (type: "team" | "league" | "event", query: string, options: Readonly<{ provider: string; signal: AbortSignal }>) => Promise<readonly SportsSearchResult[]>, config: readonly SportsDiscoveryProvider[] = providers) {
  const snapshots: SportsDiscoverySnapshot[] = [];
  const controller = new AbortController();
  const loadProviders = vi.fn(async () => config);
  const done = searchFederatedSports({ type: "team", query: " Rams ", signal: controller.signal, loadProviders, search, publish: value => snapshots.push(value), timeoutMs: 1000 });
  return { snapshots, controller, done, loadProviders };
}
describe("federated discovery", () => {
  it("skips disabled independent discovery", async () => {
    const search = vi.fn(async (_type: SportsSearchType, _query: string, options: Readonly<{ provider: string; signal: AbortSignal }>) => [team(options.provider)]);
    const value = run(search, [{ provider: "thesportsdb", enabled: true }, { provider: "espn", enabled: false }]);
    await value.done;
    expect(search).toHaveBeenCalledTimes(1);
    expect(search.mock.calls[0][2].provider).toBe("thesportsdb");
    expect(value.snapshots.at(-1)?.state).toBe("complete");
  });
  it("retains independent results while another source times out", async () => {
    vi.useFakeTimers();
    let primarySignal: AbortSignal | undefined;
    const value = run(async (_type, _query, options) => {
      if (options.provider === "espn") return [team("espn")];
      primarySignal = options.signal;
      return new Promise(() => {});
    });
    await flush();
    expect(value.snapshots.at(-1)?.results).toEqual([team("espn")]);
    expect(value.snapshots.at(-1)?.state).toBe("loading");
    await vi.advanceTimersByTimeAsync(1000);
    await value.done;
    expect(value.snapshots.at(-1)?.state).toBe("partial");
    expect(value.snapshots.at(-1)?.results).toEqual([team("espn")]);
    expect(primarySignal?.aborted).toBe(true);
  });
  it("does not merge matching IDs or names across providers", async () => {
    const value = run(async (_type, _query, options) => [team(options.provider), team(options.provider)]);
    await value.done;
    expect(value.snapshots.at(-1)?.results).toEqual([team("thesportsdb"), team("espn")]);
  });
  it("rejects mismatched provider identities and conflicting duplicates", async () => {
    const value = run(async (_type, _query, options) => options.provider === "espn"
      ? [team("espn"), { ...team("espn"), name: "Conflicting" }]
      : [team("espn")]);
    await value.done;
    expect(value.snapshots.at(-1)?.state).toBe("unavailable");
    expect(value.snapshots.at(-1)?.results).toEqual([]);
  });
  it("distinguishes fresh empty success from total source failure", async () => {
    const empty = run(async () => []);await empty.done;
    expect(empty.snapshots.at(-1)?.state).toBe("complete");
    const failed = run(async () => { throw new Error("unavailable"); });await failed.done;
    expect(failed.snapshots.at(-1)?.state).toBe("unavailable");
  });
  it("cancels pending work without publishing obsolete results", async () => {
    const signals: AbortSignal[] = [];
    const value = run(async (_type, _query, options) => { signals.push(options.signal); return new Promise(() => {}); });
    await flush();const count = value.snapshots.length;
    value.controller.abort();await value.done;
    expect(value.snapshots).toHaveLength(count);
    expect(signals.every(signal => signal.aborted)).toBe(true);
  });
  it("does not search on a blank query or unavailable capability response", async () => {
    const search = vi.fn();const publish = vi.fn();const loadProviders = vi.fn(async () => { throw new Error("failure"); });
    await searchFederatedSports({ type: "team", query: " ", signal: new AbortController().signal, loadProviders, search, publish });
    expect(loadProviders).not.toHaveBeenCalled();expect(search).not.toHaveBeenCalled();
    await searchFederatedSports({ type: "team", query: "Rams", signal: new AbortController().signal, loadProviders, search, publish });
    expect(publish.mock.lastCall?.[0].state).toBe("unavailable");expect(search).not.toHaveBeenCalled();
  });
  it("does not turn an entirely disabled configuration into an empty success", async () => {
    const search = vi.fn();const value = run(search, providers.map(row => ({ ...row, enabled: false })));await value.done;
    expect(search).not.toHaveBeenCalled();expect(value.snapshots.at(-1)?.state).toBe("unavailable");
  });
  it("rejects malformed capability records", () => {
    expect(parseDiscoveryProviders({ version: 1, providers })).toEqual(providers);
    for (const value of [{ version: 1, providers: [] }, { version: 1, providers: [providers[0], providers[0]] }, { version: 1, providers: [{ provider: "espn", enabled: "false" }, providers[0]] }, { version: 2, providers }]) {
      expect(() => parseDiscoveryProviders(value)).toThrow();
    }
  });
});
