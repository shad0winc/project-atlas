import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MediaRetention } from "../types/retention";

const { readMediaRetentionMock } = vi.hoisted(() => ({
  readMediaRetentionMock: vi.fn()
}));

vi.mock("./retention", () => ({
  readMediaRetention: readMediaRetentionMock
}));

import {
  refreshMediaRetentionAfterMutation
} from "./retention-refresh";

const scheduledRetention: MediaRetention = {
  provider: "jellyfin",
  itemId: "item-123",
  eligible: false,
  retained: true,
  lifecycle: {
    state: "scheduled",
    rule: "disliked_24h",
    basisAt: "2026-09-13T12:00:00Z",
    deleteAt: "2026-09-14T12:00:00Z"
  }
};

describe("refreshMediaRetentionAfterMutation", () => {
  beforeEach(() => {
    readMediaRetentionMock.mockReset();
  });

  it("reads authoritative retention exactly once for the mutated media identity", async () => {
    readMediaRetentionMock.mockResolvedValueOnce(
      scheduledRetention
    );

    const result =
      await refreshMediaRetentionAfterMutation(
        "jellyfin",
        "item-123"
      );

    expect(readMediaRetentionMock).toHaveBeenCalledTimes(1);

    expect(readMediaRetentionMock).toHaveBeenCalledWith(
      "jellyfin",
      "item-123"
    );

    expect(result).toEqual({
      status: "available",
      retention: scheduledRetention
    });
  });

  it("does not fan out retention reads beyond the mutated item", async () => {
    readMediaRetentionMock.mockResolvedValueOnce(
      scheduledRetention
    );

    await refreshMediaRetentionAfterMutation(
      "jellyfin",
      "item-123"
    );

    expect(readMediaRetentionMock.mock.calls).toEqual([
      ["jellyfin", "item-123"]
    ]);
  });

  it("fails closed when authoritative retention cannot be read after a successful mutation", async () => {
    readMediaRetentionMock.mockRejectedValueOnce(
      new Error("Retention unavailable.")
    );

    await expect(
      refreshMediaRetentionAfterMutation(
        "jellyfin",
        "item-123"
      )
    ).resolves.toEqual({
      status: "unavailable",
      retention: null
    });

    expect(readMediaRetentionMock).toHaveBeenCalledTimes(1);
  });

  it("does not fabricate lifecycle timing when retention refresh fails", async () => {
    readMediaRetentionMock.mockRejectedValueOnce(
      new Error("Retention unavailable.")
    );

    const result =
      await refreshMediaRetentionAfterMutation(
        "jellyfin",
        "item-123"
      );

    expect(result.retention).toBeNull();
    expect(JSON.stringify(result)).not.toContain("deleteAt");
    expect(JSON.stringify(result)).not.toContain("24");
    expect(JSON.stringify(result)).not.toContain("72");
    expect(JSON.stringify(result)).not.toContain("30");
  });

  it("preserves the exact requested item identity", async () => {
    readMediaRetentionMock.mockResolvedValueOnce({
      ...scheduledRetention,
      itemId: "ABC/123"
    });

    await refreshMediaRetentionAfterMutation(
      " JELLYFIN ",
      "ABC/123"
    );

    expect(readMediaRetentionMock).toHaveBeenCalledWith(
      " JELLYFIN ",
      "ABC/123"
    );
  });
});
