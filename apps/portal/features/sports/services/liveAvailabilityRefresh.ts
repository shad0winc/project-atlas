import type {
  SportsFollow
} from "../types/sports";

import type {
  SportsLiveAvailability
} from "./sports";

export type LiveAvailabilityLoader = (
  provider: string,
  providerEventId: string,
  options: { signal: AbortSignal }
) => Promise<SportsLiveAvailability>;

export type LiveAvailabilitySnapshot = Readonly<
  Record<string, SportsLiveAvailability>
>;

export type LiveAvailabilityRefreshOptions = Readonly<{
  follows: readonly SportsFollow[];
  load: LiveAvailabilityLoader;
  publish: (snapshot: LiveAvailabilitySnapshot) => void;
  intervalMs?: number;
}>;

/**
 * Refresh only followed-event playback eligibility.
 *
 * Each refresh invalidates previously published availability.
 * Aborted and superseded requests cannot publish stale results.
 * This service never creates a playback session or bypasses
 * the Sports backend's authoritative availability response.
 */
export function startLiveAvailabilityRefresh({
  follows,
  load,
  publish,
  intervalMs = 30_000
}: LiveAvailabilityRefreshOptions): () => void {
  const eventFollows = follows.filter(
    (follow) => follow.type === "event" && follow.enabled
  );

  let activeController: AbortController | null = null;
  let generation = 0;
  let stopped = false;

  function invalidate(): void {
    generation += 1;
    activeController?.abort();
    activeController = null;

    if (!stopped) {
      publish({});
    }
  }

  async function refresh(): Promise<void> {
    if (stopped) {
      return;
    }

    if (document.visibilityState === "hidden") {
      invalidate();
      return;
    }

    activeController?.abort();

    const controller = new AbortController();
    activeController = controller;

    const currentGeneration = ++generation;

    // Previous availability is not authorization for this refresh.
    publish({});

    const results = await Promise.all(
      eventFollows.map(async (follow) => {
        const identity =
          `${follow.provider}:${follow.providerId}`;

        try {
          const availability = await load(
            follow.provider,
            follow.providerId,
            { signal: controller.signal }
          );

          return [identity, availability] as const;
        } catch {
          return null;
        }
      })
    );

    if (
      stopped ||
      controller.signal.aborted ||
      currentGeneration !== generation
    ) {
      return;
    }

    const snapshot: Record<string, SportsLiveAvailability> = {};

    for (const result of results) {
      if (result !== null) {
        snapshot[result[0]] = result[1];
      }
    }

    activeController = null;
    publish(snapshot);
  }

  function onVisibilityChange(): void {
    if (document.visibilityState === "hidden") {
      invalidate();
    } else {
      void refresh();
    }
  }

  void refresh();

  const interval = window.setInterval(() => {
    if (document.visibilityState !== "hidden") {
      void refresh();
    }
  }, intervalMs);

  document.addEventListener(
    "visibilitychange",
    onVisibilityChange
  );

  return () => {
    if (stopped) {
      return;
    }

    stopped = true;
    generation += 1;

    window.clearInterval(interval);

    document.removeEventListener(
      "visibilitychange",
      onVisibilityChange
    );

    activeController?.abort();
    activeController = null;
  };
}
