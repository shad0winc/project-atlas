import type { SubtitleSelection } from "../../playback/services/session";
import { createSportsLiveSession, releaseSportsLiveSession, type SportsLiveSessionResult } from "./sports";

/** Never open a replacement until the previous owned session has closed successfully. */
export async function replaceSportsLiveSession({ current, channelId, optionId, signal, subtitle = "auto", detach }: Readonly<{
  current: SportsLiveSessionResult | null;
  channelId: string;
  optionId?: string;
  signal?: AbortSignal;
  subtitle?: SubtitleSelection;
  detach: () => void;
}>): Promise<SportsLiveSessionResult> {
  if (current !== null) {
    detach();
    // Do not pass the new request's abort signal to cleanup of an existing stream.
    await releaseSportsLiveSession(current.liveSessionId);
  }
  if (signal?.aborted) throw new Error("Live playback request was cancelled.");
  return createSportsLiveSession(channelId, { signal }, subtitle, optionId);
}
