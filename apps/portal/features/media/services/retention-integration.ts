import type { MediaRetentionRefreshResult } from "./retention-refresh";

import type { MediaRetention } from "../types/retention";

function retentionIdentity(
  provider: string,
  itemId: string
): string {
  return `${provider}\u0000${itemId}`;
}

export function applyMediaRetentionRefreshResult(
  current: ReadonlyMap<string, MediaRetention>,
  provider: string,
  itemId: string,
  result: MediaRetentionRefreshResult
): ReadonlyMap<string, MediaRetention> {
  const next = new Map(current);

  const identity =
    retentionIdentity(provider, itemId);

  if (result.status === "available") {
    next.set(identity, result.retention);
  } else {
    next.delete(identity);
  }

  return next;
}
