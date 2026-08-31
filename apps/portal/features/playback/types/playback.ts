export const PLAYBACK_ACTIONS = [
  "watch_now",
  "watch_live",
  "watch_recording"
] as const;

export type PlaybackActionKind = (typeof PLAYBACK_ACTIONS)[number];
export type PlaybackSourceType = "library" | "live" | "recording";

export type PlaybackAction = Readonly<{
  available: boolean;
  action: PlaybackActionKind;
  label: string;
  backend: string;
  sourceType: PlaybackSourceType;
  provider: string;
  targetId: string;
  href?: string;
}>;

export function createPlaybackAction(input: PlaybackAction): PlaybackAction {
  const provider = input.provider.trim().toLowerCase();
  const backend = input.backend.trim().toLowerCase();
  const targetId = input.targetId.trim();
  const label = input.label.trim();
  const href = input.href?.trim();

  if (!provider || !backend || !targetId || !label) {
    throw new Error("Playback action contains an empty required field.");
  }

  if (!PLAYBACK_ACTIONS.includes(input.action)) {
    throw new Error("Playback action is invalid.");
  }

  return Object.freeze({
    ...input,
    provider,
    backend,
    targetId,
    label,
    ...(href ? { href } : {})
  });
}
