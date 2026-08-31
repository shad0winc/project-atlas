import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createPlaybackAction,
  type PlaybackAction
} from "../types/playback";

type PlaybackActionTransportResponse = Readonly<{
  available: boolean;
  action: "watch_now" | "watch_live" | "watch_recording";
  label: string;
  backend: string;
  source_type: "library" | "live" | "recording";
  provider: string;
  target_id: string;
  href: string | null;
}>;

export type ResolvePlaybackOptions = Readonly<{
  signal?: AbortSignal;
}>;

export async function resolvePlaybackAction(
  provider: string,
  itemId: string,
  { signal }: ResolvePlaybackOptions = {}
): Promise<PlaybackAction> {
  const normalizedProvider = provider.trim().toLowerCase();
  const normalizedItemId = itemId.trim();

  if (!normalizedProvider) {
    throw new Error("playback.provider must not be empty.");
  }

  if (!normalizedItemId) {
    throw new Error("playback.itemId must not be empty.");
  }

  const response =
    await authenticatedAtlasApiRequest<PlaybackActionTransportResponse>(
      `/media/playback/${encodeURIComponent(normalizedProvider)}/${encodeURIComponent(normalizedItemId)}`,
      {
        method: "GET",
        cache: "no-store",
        signal
      }
    );

  const action = createPlaybackAction({
    available: response.available,
    action: response.action,
    label: response.label,
    backend: response.backend,
    sourceType: response.source_type,
    provider: response.provider,
    targetId: response.target_id,
    ...(response.href === null ? {} : { href: response.href })
  });

  if (
    action.provider !== normalizedProvider ||
    action.targetId !== normalizedItemId
  ) {
    throw new Error(
      "Playback response did not match the requested media identity."
    );
  }

  return action;
}
