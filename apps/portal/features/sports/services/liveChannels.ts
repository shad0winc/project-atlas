import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type SportsLiveChannel = Readonly<{
  atlasChannelId: string;
  name: string;
  playbackConfigured: boolean;
}>;

export function parseSportsLiveChannels(
  payload: unknown,
): readonly SportsLiveChannel[] {
  if (
    typeof payload !== "object" ||
    payload === null ||
    !("channels" in payload) ||
    !Array.isArray(payload.channels)
  ) {
    throw new Error("Atlas returned invalid live channel information.");
  }
  const seen = new Set<string>();
  return Object.freeze(
    payload.channels.map((row: unknown) => {
      if (
        typeof row !== "object" ||
        row === null ||
        !("atlas_channel_id" in row) ||
        !("name" in row) ||
        !("playback_configured" in row) ||
        typeof row.atlas_channel_id !== "string" ||
        !row.atlas_channel_id.startsWith("sports-live-") ||
        row.atlas_channel_id.length <= 12 ||
        typeof row.name !== "string" ||
        !row.name.trim() ||
        typeof row.playback_configured !== "boolean" ||
        seen.has(row.atlas_channel_id)
      ) {
        throw new Error("Atlas returned invalid live channel information.");
      }
      seen.add(row.atlas_channel_id);
      return Object.freeze({
        atlasChannelId: row.atlas_channel_id,
        name: row.name.trim(),
        playbackConfigured: row.playback_configured,
      });
    }),
  );
}

export async function loadSportsLiveChannels(
  signal?: AbortSignal,
): Promise<readonly SportsLiveChannel[]> {
  const payload = await authenticatedAtlasApiRequest<unknown>(
    "/sports/live-channels",
    {
      method: "GET",
      cache: "no-store",
      signal,
    },
  );
  return parseSportsLiveChannels(payload);
}
