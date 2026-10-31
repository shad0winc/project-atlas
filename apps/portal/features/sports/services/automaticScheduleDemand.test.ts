import assert from "node:assert/strict";
import { describe, it } from "vitest";
import { automaticScheduleDemand, manualScheduleDemand } from "./automaticScheduleDemand";
import { startFollowedSportsRefresh } from "./followedSportsRefresh";
import type { SportsFollow } from "../types/sports";

const follow = (provider: string, type: SportsFollow["type"], id: string, enabled = true): SportsFollow => ({
  provider, type, providerId: id, enabled, subscriptionId: provider + ":" + id,
  name: "Fixture", userId: "fixture", record: false, createdAt: null,
});
const follows = [follow("thesportsdb", "league", "4391"), follow("espn", "league", "football/nfl")];
const browse = { provider: "thesportsdb", type: "league" as const, providerId: "4387" };

function automaticLoads(mode: boolean | null | undefined): string[] {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "document");
  Object.defineProperty(globalThis, "document", { configurable: true, value: {
    visibilityState: "visible", addEventListener() {}, removeEventListener() {},
  } });
  const loaded: string[] = [];
  try {
    const input = automaticScheduleDemand(follows, browse, mode);
    const stop = startFollowedSportsRefresh({ ...input,
      load: async (_options, filter) => { loaded.push(filter.provider ?? ""); return []; }, publish() {},
    });
    stop();
  } finally {
    if (descriptor) Object.defineProperty(globalThis, "document", descriptor);
    else Reflect.deleteProperty(globalThis, "document");
  }
  return loaded;
}

describe("automatic Sports provider demand", () => {
  for (const mode of [true, null, undefined]) {
    it(`keeps search-provider GETs out of the real polling loop for ${String(mode)}`, () => {
      assert.deepEqual(automaticLoads(mode), ["espn"]);
    });
  }
  it("preserves original polling when the catalog is explicitly disabled", () => {
    assert.deepEqual(automaticLoads(false), ["thesportsdb", "espn"]);
  });
  it("does not mutate follows or remap provider identities", () => {
    const result = automaticScheduleDemand(follows, browse, true);
    assert.equal(follows.length, 2); assert.equal(result.follows[0], follows[1]);
    assert.equal(result.browse, undefined);
  });
  it("keeps an explicit ESPN selection in cache-only automatic reads", () => {
    const selected = { provider: "espn", type: "league" as const, providerId: "basketball/nba" };
    assert.equal(automaticScheduleDemand(follows, selected, true).browse, selected);
  });
  it("manual browse includes only its provider's enabled follows and explicit selection", () => {
    const result = manualScheduleDemand([...follows, follow("thesportsdb", "team", "team-1"),
      follow("thesportsdb", "channel", "channel-1"), follow("thesportsdb", "event", "disabled", false)], browse);
    assert.deepEqual(result, { provider: "thesportsdb", eventIds: [], teamIds: ["team-1"], leagueIds: ["4391", "4387"] });
  });
  it("manual browse deduplicates identifiers", () => {
    const result = manualScheduleDemand([follows[0], follows[0]], { ...browse, providerId: "4391" });
    assert.deepEqual(result.leagueIds, ["4391"]);
  });
  it("refuses blank manual identities instead of requesting an unfiltered schedule", () => {
    assert.throws(() => manualScheduleDemand(follows, { ...browse, providerId: " " }));
    assert.throws(() => manualScheduleDemand(follows, { ...browse, provider: " " }));
  });
});
