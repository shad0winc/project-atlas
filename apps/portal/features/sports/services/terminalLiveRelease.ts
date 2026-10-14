import type { PlaybackSession } from "../../playback/types/session";
import type { SportsLiveSessionResult } from "./sports";

/** Retain exact ownership until release succeeds. No timers or automatic retries. */
export function createTerminalLiveRelease() {
  let failed: SportsLiveSessionResult | null = null;
  let pending: Promise<boolean> | null = null;
  return {
    current: () => failed,
    blocksHeartbeat: (sessionId: string) => failed?.liveSessionId === sessionId,
    markFailed(current: SportsLiveSessionResult | null, playback: PlaybackSession): boolean {
      if (failed !== null || current === null || current.session !== playback) return false;
      failed = current;
      return true;
    },
    release(close: (owned: SportsLiveSessionResult) => Promise<unknown>): Promise<boolean> {
      if (pending !== null) return pending;
      if (failed === null) return Promise.resolve(true);
      const owned = failed;
      pending = Promise.resolve().then(() => close(owned)).then(
        () => { if (failed === owned) failed = null; return true; },
        () => false,
      ).finally(() => { pending = null; });
      return pending;
    },
  };
}
