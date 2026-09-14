import { describe, expect, it } from "vitest";

import {
  createMediaRetention,
  type MediaRetention
} from "./retention";

function retention(
  overrides: Partial<MediaRetention> = {}
): MediaRetention {
  return {
    provider: "jellyfin",
    itemId: "item-123",
    eligible: false,
    retained: true,
    lifecycle: {
      state: "scheduled",
      rule: "unwatched_30d",
      basisAt: "2026-08-15T00:00:00Z",
      deleteAt: "2026-09-14T00:00:00Z"
    },
    ...overrides
  };
}

describe("media retention domain contract", () => {
  it("accepts authoritative scheduled lifecycle timestamps without recomputing them", () => {
    expect(createMediaRetention(retention())).toEqual({
      provider: "jellyfin",
      itemId: "item-123",
      eligible: false,
      retained: true,
      lifecycle: {
        state: "scheduled",
        rule: "unwatched_30d",
        basisAt: "2026-08-15T00:00:00Z",
        deleteAt: "2026-09-14T00:00:00Z"
      }
    });
  });

  it("accepts protected lifecycle without a fake deletion deadline", () => {
    const value = createMediaRetention(
      retention({
        lifecycle: {
          state: "protected",
          rule: "policy_protected",
          basisAt: null,
          deleteAt: null
        }
      })
    );

    expect(value.lifecycle).toEqual({
      state: "protected",
      rule: "policy_protected",
      basisAt: null,
      deleteAt: null
    });

    expect(value.eligible).toBe(false);
    expect(value.retained).toBe(true);
  });

  it("accepts eligible disliked lifecycle with authoritative deleteAt", () => {
    const value = createMediaRetention(
      retention({
        eligible: true,
        retained: false,
        lifecycle: {
          state: "eligible",
          rule: "disliked_24h",
          basisAt: "2026-09-13T00:00:00Z",
          deleteAt: "2026-09-14T00:00:00Z"
        }
      })
    );

    expect(value.lifecycle.state).toBe("eligible");
    expect(value.lifecycle.rule).toBe("disliked_24h");
    expect(value.lifecycle.deleteAt).toBe("2026-09-14T00:00:00Z");
  });

  it("accepts unknown unavailable lifecycle without inventing timing", () => {
    const value = createMediaRetention(
      retention({
        lifecycle: {
          state: "unknown",
          rule: "unavailable",
          basisAt: null,
          deleteAt: null
        }
      })
    );

    expect(value.lifecycle).toEqual({
      state: "unknown",
      rule: "unavailable",
      basisAt: null,
      deleteAt: null
    });
  });

  it("rejects eligible and retained being true together", () => {
    expect(() =>
      createMediaRetention(
        retention({
          eligible: true,
          retained: true
        })
      )
    ).toThrow();
  });

  it("rejects a scheduled lifecycle without authoritative deleteAt", () => {
    expect(() =>
      createMediaRetention(
        retention({
          lifecycle: {
            state: "scheduled",
            rule: "unwatched_30d",
            basisAt: "2026-08-15T00:00:00Z",
            deleteAt: null
          }
        })
      )
    ).toThrow();
  });

  it("rejects a protected lifecycle carrying a deletion deadline", () => {
    expect(() =>
      createMediaRetention(
        retention({
          lifecycle: {
            state: "protected",
            rule: "policy_protected",
            basisAt: null,
            deleteAt: "2037-01-01T00:00:00Z"
          }
        })
      )
    ).toThrow();
  });

  it("preserves item identity exactly while normalizing provider case", () => {
    const value = createMediaRetention(
      retention({
        provider: " JELLYFIN ",
        itemId: "ABC-123"
      })
    );

    expect(value.provider).toBe("jellyfin");
    expect(value.itemId).toBe("ABC-123");
  });
  it("preserves legacy eligibility without inventing a lifecycle deadline", () => {
    const value = createMediaRetention(
      retention({
        eligible: true,
        retained: false,
        lifecycle: {
          state: "unknown",
          rule: "legacy",
          basisAt: null,
          deleteAt: null
        }
      })
    );

    expect(value).toEqual({
      provider: "jellyfin",
      itemId: "item-123",
      eligible: true,
      retained: false,
      lifecycle: {
        state: "unknown",
        rule: "legacy",
        basisAt: null,
        deleteAt: null
      }
    });
  });

});
