import {
  resolvePlaybackAction,
  type ResolvePlaybackOptions
} from "../services/playback";

import type { PlaybackAction } from "../types/playback";

export type LoadPlaybackActionOptions = ResolvePlaybackOptions;

export async function loadPlaybackAction(
  provider: string,
  itemId: string,
  options: LoadPlaybackActionOptions = {}
): Promise<PlaybackAction> {
  return resolvePlaybackAction(provider, itemId, options);
}
