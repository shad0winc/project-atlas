import { describe, expect, it } from "vitest";

import type {
  SportsEvent,
  SportsFollow
} from "../types/sports";

import {
  reconcileFollowedEventMetadata
} from "./followedEventMetadata";

const original: SportsEvent = {
  provider: "thesportsdb",
  providerEventId: "event-001",
  name: "Atlas Rams vs Atlas Giants",
  sport: "American Football",
  league: "NFL",
  startAt: "2026-09-20T20:25:00.000Z",
  status: "scheduled",
  requested: true
};

const follow: SportsFollow = {
  subscriptionId: "sub-001",
  type: "event",
  provider: "thesportsdb",
  providerId: "event-001",
  name: original.name,
  userId: "usr-001",
  enabled: true,
  record: false,
  createdAt: "2026-09-19T20:00:00.000Z"
};

describe("followed-event metadata reconciliation", () => {
  it("retains last-known metadata after a provider failure", () => {
    const result = reconcileFollowedEventMetadata(
      [original],
      [follow],
      ["thesportsdb"],
      [{ status: "rejected", reason: new Error("Unavailable") }]
    );

    expect(result).toEqual([original]);
  });

  it("retains an event omitted from a successful partial lookup", () => {
    const result = reconcileFollowedEventMetadata(
      [original],
      [follow],
      ["thesportsdb"],
      [{ status: "fulfilled", value: [] }]
    );

    expect(result).toEqual([original]);
  });

  it("updates metadata when the provider returns that event", () => {
    const updated: SportsEvent = {
      ...original,
      startAt: "2026-09-20T21:25:00.000Z",
      status: "delayed"
    };

    const result = reconcileFollowedEventMetadata(
      [original],
      [follow],
      ["thesportsdb"],
      [{ status: "fulfilled", value: [updated] }]
    );

    expect(result).toEqual([updated]);
  });

  it("removes metadata when the event is no longer followed", () => {
    const result = reconcileFollowedEventMetadata(
      [original],
      [],
      ["thesportsdb"],
      [{ status: "rejected", reason: new Error("Unavailable") }]
    );

    expect(result).toEqual([]);
  });

  it("does not mix provider identities with the same event ID", () => {
    const other: SportsEvent = {
      ...original,
      provider: "other-provider",
      startAt: "2026-09-20T22:25:00.000Z"
    };

    const otherFollow: SportsFollow = {
      ...follow,
      subscriptionId: "sub-other",
      provider: "other-provider"
    };

    const result = reconcileFollowedEventMetadata(
      [original, other],
      [follow, otherFollow],
      ["thesportsdb", "other-provider"],
      [
        { status: "fulfilled", value: [{ ...original, status: "live" }] },
        { status: "rejected", reason: new Error("Unavailable") }
      ]
    );

    expect(result).toEqual([
      { ...original, status: "live" },
      other
    ]);
  });

  it("ignores returned events that are not actively followed", () => {
    const result = reconcileFollowedEventMetadata(
      [],
      [follow],
      ["thesportsdb"],
      [{
        status: "fulfilled",
        value: [
          original,
          { ...original, providerEventId: "not-followed" }
        ]
      }]
    );

    expect(result).toEqual([original]);
  });
});
