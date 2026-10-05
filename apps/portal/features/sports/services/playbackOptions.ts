import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type SportsPlaybackOption = Readonly<{
  optionId: "primary" | "backup-1" | "backup-2";
  label: string;
  configured: boolean;
}>;

export function parseSportsPlaybackOptions(payload: unknown): readonly SportsPlaybackOption[] {
  if (typeof payload !== "object" || payload === null || !("options" in payload) || !Array.isArray(payload.options) || payload.options.length > 3)
    throw new Error("Atlas returned invalid playback choices.");
  const ids = ["primary", "backup-1", "backup-2"] as const;
  return Object.freeze(payload.options.map((row: unknown, index: number) => {
    const optionId = ids[index];
    if (optionId === undefined || typeof row !== "object" || row === null || !("option_id" in row) || row.option_id !== optionId ||
        !("label" in row) || typeof row.label !== "string" || !row.label.trim() || row.label.length > 80 ||
        !("configured" in row) || typeof row.configured !== "boolean" ||
        Object.keys(row).some(key => !["option_id", "label", "configured"].includes(key)))
      throw new Error("Atlas returned invalid playback choices.");
    return Object.freeze({ optionId, label: row.label, configured: row.configured });
  }));
}

export async function loadSportsPlaybackOptions(channelId: string, signal?: AbortSignal): Promise<readonly SportsPlaybackOption[]> {
  const payload = await authenticatedAtlasApiRequest<unknown>(`/sports/live/${encodeURIComponent(channelId)}/options`, {
    method: "GET", cache: "no-store", signal,
  });
  return parseSportsPlaybackOptions(payload);
}

export function preferredSportsPlaybackOption(options: readonly SportsPlaybackOption[]): SportsPlaybackOption["optionId"] | undefined {
  const primary = options[0];
  if (primary === undefined) return undefined;
  if (primary.optionId !== "primary" || !primary.configured)
    throw new Error("Primary playback setup is pending.");
  return primary.optionId;
}
