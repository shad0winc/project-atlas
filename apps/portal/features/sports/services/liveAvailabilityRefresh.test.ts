import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SportsFollow } from "../types/sports";
import type { SportsLiveAvailability } from "./sports";
import {
  startLiveAvailabilityRefresh
} from "./liveAvailabilityRefresh";

const follow: SportsFollow = {
  subscriptionId: "sub-001",
  type: "event",
  provider: "thesportsdb",
  providerId: "event-001",
  name: "Atlas Rams vs Atlas Giants",
  userId: "usr-001",
  enabled: true,
  record: false,
  createdAt: "2026-09-19T20:00:00.000Z"
};

const available: SportsLiveAvailability = {
  available: true,
  atlasChannelId: "sports-live-source-001"
};

const unavailable: SportsLiveAvailability = {
  available: false,
  atlasChannelId: null
};

type VisibilityDocument = {
  visibilityState: "visible" | "hidden";
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
};

let visibilityDocument: VisibilityDocument;
let onVisibilityChange: (() => void) | undefined;

async function settle(): Promise<void> {
  for (let i = 0; i < 8; i += 1) {
    await Promise.resolve();
  }
}

beforeEach(() => {
  vi.useFakeTimers();

  onVisibilityChange = undefined;

  visibilityDocument = {
    visibilityState: "visible",

    addEventListener: vi.fn((name: string, listener: () => void) => {
      if (name === "visibilitychange") {
        onVisibilityChange = listener;
      }
    }),

    removeEventListener: vi.fn((name: string, listener: () => void) => {
      if (name === "visibilitychange" && onVisibilityChange === listener) {
        onVisibilityChange = undefined;
      }
    })
  };

  vi.stubGlobal("document", visibilityDocument);

  vi.stubGlobal("window", {
    setInterval: globalThis.setInterval,
    clearInterval: globalThis.clearInterval
  });
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("followed-event live availability refresh", () => {
  it("loads immediately and refreshes every 30 seconds while visible", async () => {
    const load = vi.fn(async () => available);
    const publish = vi.fn();

    const stop = startLiveAvailabilityRefresh({
      follows: [follow],
      load,
      publish
    });

    try {
      await settle();

      expect(load).toHaveBeenCalledOnce();
      expect(load).toHaveBeenCalledWith(
        "thesportsdb",
        "event-001",
        { signal: expect.any(AbortSignal) }
      );
      expect(publish).toHaveBeenLastCalledWith({
        "thesportsdb:event-001": available
      });

      await vi.advanceTimersByTimeAsync(30_000);
      await settle();

      expect(load).toHaveBeenCalledTimes(2);
      expect(publish).toHaveBeenLastCalledWith({
        "thesportsdb:event-001": available
      });
    } finally {
      stop();
    }
  });

  it("invalidates availability while hidden and rechecks on return", async () => {
    const load = vi.fn(async () => available);
    const publish = vi.fn();

    const stop = startLiveAvailabilityRefresh({
      follows: [follow],
      load,
      publish
    });

    try {
      await settle();
      expect(publish).toHaveBeenLastCalledWith({
        "thesportsdb:event-001": available
      });

      visibilityDocument.visibilityState = "hidden";
      onVisibilityChange?.();

      expect(publish).toHaveBeenLastCalledWith({});

      await vi.advanceTimersByTimeAsync(60_000);
      expect(load).toHaveBeenCalledOnce();

      visibilityDocument.visibilityState = "visible";
      onVisibilityChange?.();
      await settle();

      expect(load).toHaveBeenCalledTimes(2);
      expect(publish).toHaveBeenLastCalledWith({
        "thesportsdb:event-001": available
      });
    } finally {
      stop();
    }
  });

  it("does not restore availability from a superseded request", async () => {
    let resolveFirst!: (value: SportsLiveAvailability) => void;

    const first = new Promise<SportsLiveAvailability>((resolve) => {
      resolveFirst = resolve;
    });

    const load = vi.fn()
      .mockImplementationOnce(() => first)
      .mockResolvedValueOnce(unavailable);

    const publish = vi.fn();

    const stop = startLiveAvailabilityRefresh({
      follows: [follow],
      load,
      publish
    });

    try {
      expect(load).toHaveBeenCalledOnce();

      const firstSignal = load.mock.calls[0]?.[2]?.signal as
        | AbortSignal
        | undefined;

      await vi.advanceTimersByTimeAsync(30_000);
      await settle();

      expect(firstSignal?.aborted).toBe(true);
      expect(load).toHaveBeenCalledTimes(2);
      expect(publish).toHaveBeenLastCalledWith({
        "thesportsdb:event-001": unavailable
      });

      const publishCount = publish.mock.calls.length;

      // Simulate a transport that resolves despite cancellation.
      resolveFirst(available);
      await settle();

      expect(publish).toHaveBeenCalledTimes(publishCount);
      expect(publish).toHaveBeenLastCalledWith({
        "thesportsdb:event-001": unavailable
      });
    } finally {
      stop();
    }
  });

  it("clears previously available playback when a refresh fails", async () => {
    const load = vi.fn()
      .mockResolvedValueOnce(available)
      .mockRejectedValueOnce(new Error("Availability service unavailable"));

    const publish = vi.fn();

    const stop = startLiveAvailabilityRefresh({
      follows: [follow],
      load,
      publish
    });

    try {
      await settle();

      expect(publish).toHaveBeenLastCalledWith({
        "thesportsdb:event-001": available
      });

      await vi.advanceTimersByTimeAsync(30_000);
      await settle();

      expect(load).toHaveBeenCalledTimes(2);
      expect(publish).toHaveBeenLastCalledWith({});
    } finally {
      stop();
    }
  });

  it("aborts outstanding work and prevents publication after cleanup", async () => {
    let resolvePending!: (value: SportsLiveAvailability) => void;

    const pending = new Promise<SportsLiveAvailability>((resolve) => {
      resolvePending = resolve;
    });

    const load = vi.fn(
      (
        provider: string,
        providerEventId: string,
        options: { signal: AbortSignal }
      ) => {
        expect(provider).toBe("thesportsdb");
        expect(providerEventId).toBe("event-001");
        expect(options.signal).toBeInstanceOf(AbortSignal);
        return pending;
      }
    );
    const publish = vi.fn();

    const stop = startLiveAvailabilityRefresh({
      follows: [follow],
      load,
      publish
    });

    const signal = load.mock.calls[0]?.[2]?.signal;

    const publishCount = publish.mock.calls.length;

    stop();

    expect(signal?.aborted).toBe(true);
    expect(
      visibilityDocument.removeEventListener
    ).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function)
    );

    resolvePending(available);
    await settle();
    await vi.advanceTimersByTimeAsync(60_000);

    expect(load).toHaveBeenCalledOnce();
    expect(publish).toHaveBeenCalledTimes(publishCount);
  });
});
