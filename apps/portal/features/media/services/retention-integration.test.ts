import { describe, expect, it } from "vitest";

import type { MediaRetention } from "../types/retention";

import {
  applyMediaRetentionRefreshResult
} from "./retention-integration";

const retention: MediaRetention = {
  provider: "jellyfin",
  itemId: "item-123",
  eligible: false,
  retained: true,
  lifecycle: {
    state: "protected",
    rule: "policy_protected",
    basisAt: null,
    deleteAt: null
  }
};

describe("applyMediaRetentionRefreshResult", () => {
  it("stores authoritative available retention under the exact media identity", () => {
    const current =
      new Map<string, MediaRetention>();

    const next =
      applyMediaRetentionRefreshResult(
        current,
        "jellyfin",
        "item-123",
        {
          status: "available",
          retention
        }
      );

    expect(next).not.toBe(current);

    expect(
      next.get("jellyfin\u0000item-123")
    ).toEqual(retention);
  });

  it("removes stale retention when the authoritative refresh is unavailable", () => {
    const current =
      new Map<string, MediaRetention>([
        [
          "jellyfin\u0000item-123",
          retention
        ]
      ]);

    const next =
      applyMediaRetentionRefreshResult(
        current,
        "jellyfin",
        "item-123",
        {
          status: "unavailable",
          retention: null
        }
      );

    expect(next).not.toBe(current);

    expect(
      next.has("jellyfin\u0000item-123")
    ).toBe(false);
  });

  it("preserves unrelated retained media state", () => {
    const other: MediaRetention = {
      ...retention,
      itemId: "other-item"
    };

    const current =
      new Map<string, MediaRetention>([
        [
          "jellyfin\u0000other-item",
          other
        ]
      ]);

    const next =
      applyMediaRetentionRefreshResult(
        current,
        "jellyfin",
        "item-123",
        {
          status: "available",
          retention
        }
      );

    expect(
      next.get("jellyfin\u0000other-item")
    ).toEqual(other);

    expect(
      next.get("jellyfin\u0000item-123")
    ).toEqual(retention);
  });

  it("does not mutate the existing map", () => {
    const current =
      new Map<string, MediaRetention>();

    applyMediaRetentionRefreshResult(
      current,
      "jellyfin",
      "item-123",
      {
        status: "available",
        retention
      }
    );

    expect(current.size).toBe(0);
  });
});
