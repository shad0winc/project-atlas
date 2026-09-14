import { readMediaRetention } from "./retention";

import type { MediaRetention } from "../types/retention";

export type MediaRetentionRefreshResult =
  | Readonly<{
      status: "available";
      retention: MediaRetention;
    }>
  | Readonly<{
      status: "unavailable";
      retention: null;
    }>;

export async function refreshMediaRetentionAfterMutation(
  provider: string,
  itemId: string
): Promise<MediaRetentionRefreshResult> {
  try {
    const retention =
      await readMediaRetention(provider, itemId);

    return {
      status: "available",
      retention
    };
  } catch {
    return {
      status: "unavailable",
      retention: null
    };
  }
}
