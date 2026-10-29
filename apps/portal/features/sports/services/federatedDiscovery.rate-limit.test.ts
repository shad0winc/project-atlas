import { describe, expect, it, vi } from "vitest";
import { searchFederatedSports, SportsDiscoveryRateLimitError, type SportsDiscoverySnapshot } from "./federatedDiscovery";

const providers = [{ provider: "thesportsdb", enabled: true }] as const;
async function run(search: Parameters<typeof searchFederatedSports>[0]["search"], sources: Parameters<typeof searchFederatedSports>[0]["loadProviders"] = async () => providers, timeoutMs = 1000) {
  const snapshots: SportsDiscoverySnapshot[] = [];
  await searchFederatedSports({ type: "league", query: "NBA", signal: new AbortController().signal,
    loadProviders: sources, search, publish: snapshot => snapshots.push(snapshot), timeoutMs });
  return snapshots.at(-1)!;
}
describe("federated discovery rate-limit reporting", () => {
  it("preserves a classified rate limit without retrying", async () => {
    const search = vi.fn(async () => { throw new SportsDiscoveryRateLimitError(); });
    const result = await run(search);
    expect(result.state).toBe("unavailable");
    expect(result.sources).toEqual([{ provider: "thesportsdb", outcome: "unavailable", reason: "rate-limit" }]);
    expect(search).toHaveBeenCalledTimes(1);
  });
  it("retains another provider's results during a throttle", async () => {
    const result = await run(async (_type, _query, { provider }) => {
      if (provider === "thesportsdb") throw new SportsDiscoveryRateLimitError();
      return [{ kind: "league", provider: "espn", id: "nba", name: "NBA", sport: "Basketball", league: "NBA" }];
    }, async () => [{ provider: "thesportsdb", enabled: true }, { provider: "espn", enabled: true }]);
    expect(result.state).toBe("partial");
    expect(result.results).toHaveLength(1);
    expect(result.sources[0].reason).toBe("rate-limit");
  });
  it("does not misclassify other errors or expose their text", async () => {
    const result = await run(async () => { throw new Error("private backend detail"); });
    expect(result.state).toBe("unavailable");
    expect(result.sources[0].reason).toBeUndefined();
    expect(JSON.stringify(result)).not.toContain("private backend detail");
  });
  it("keeps successful empty search distinct from unavailability", async () => {
    const result = await run(async () => []);
    expect(result.state).toBe("complete");
    expect(result.sources[0].reason).toBeUndefined();
  });
  it("does not label a timeout as throttling", async () => {
    const result = await run(async () => new Promise<readonly never[]>(() => {}), undefined, 5);
    expect(result.state).toBe("unavailable");
    expect(result.sources[0].reason).toBeUndefined();
  });
});
