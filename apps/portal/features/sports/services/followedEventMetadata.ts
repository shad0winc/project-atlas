import type {
  SportsEvent,
  SportsFollow
} from "../types/sports";

/**
 * Reconcile independently fetched Following metadata.
 *
 * A missing event in an otherwise successful provider response is
 * not proof of cancellation or deletion. Preserve its last-known
 * metadata until the user no longer follows it or a newer event
 * record is returned.
 */
export function reconcileFollowedEventMetadata(
  current: readonly SportsEvent[],
  follows: readonly SportsFollow[],
  providers: readonly string[],
  results: readonly PromiseSettledResult<readonly SportsEvent[]>[]
): readonly SportsEvent[] {
  const activeIdentities = new Set(
    follows
      .filter(
        (follow) =>
          follow.type === "event" && follow.enabled
      )
      .map(
        (follow) =>
          `${follow.provider}:${follow.providerId}`
      )
  );

  const retained = new Map<string, SportsEvent>();

  for (const event of current) {
    const identity =
      `${event.provider}:${event.providerEventId}`;

    if (activeIdentities.has(identity)) {
      retained.set(identity, event);
    }
  }

  results.forEach((result, index) => {
    if (result.status !== "fulfilled") {
      return;
    }

    const provider = providers[index];

    if (provider === undefined) {
      return;
    }

    for (const event of result.value) {
      const identity =
        `${event.provider}:${event.providerEventId}`;

      if (
        event.provider === provider &&
        activeIdentities.has(identity)
      ) {
        retained.set(identity, event);
      }
    }
  });

  return Array.from(retained.values());
}
