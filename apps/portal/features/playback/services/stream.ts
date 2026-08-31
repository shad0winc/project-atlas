import type { PlaybackSession } from "../types/session";

const PLAYBACK_ORIGIN = "https://playback.shadowinc.co";
const BOOTSTRAP_PATH = "/_atlas/playback/bootstrap";

type PlaybackBootstrapTransport = Readonly<{
  stream_url: string;
}>;

export type PlaybackStream = Readonly<{
  streamUrl: string;
}>;

function validateBootstrapUrl(value: string): URL {
  const url = new URL(value);

  if (
    url.origin !== PLAYBACK_ORIGIN ||
    url.pathname !== BOOTSTRAP_PATH ||
    url.search ||
    url.hash
  ) {
    throw new Error("Playback bootstrap endpoint is not trusted.");
  }

  return url;
}

function validateStreamUrl(value: string): string {
  const url = new URL(value);

  if (
    url.origin !== PLAYBACK_ORIGIN ||
    !url.pathname.startsWith("/videos/") ||
    url.hash
  ) {
    throw new Error("Playback stream endpoint is not trusted.");
  }

  const forbidden = new Set([
    "apikey",
    "api_key",
    "token",
    "x-emby-token"
  ]);

  for (const key of url.searchParams.keys()) {
    if (forbidden.has(key.toLowerCase())) {
      throw new Error("Playback stream exposed authentication material.");
    }
  }

  return url.toString();
}

export async function bootstrapPlaybackStream(
  session: PlaybackSession,
  signal?: AbortSignal
): Promise<PlaybackStream> {
  const capability = session.playbackCapability.trim();
  if (!capability) {
    throw new Error("Playback capability is unavailable.");
  }

  const bootstrapUrl = validateBootstrapUrl(session.playbackBootstrapUrl);

  const response = await fetch(bootstrapUrl, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${capability}`
    },
    signal
  });

  if (!response.ok) {
    throw new Error(
      response.status === 401
        ? "Playback authorization expired. Try again."
        : "Atlas could not establish the secure playback connection."
    );
  }

  const payload = (await response.json()) as Partial<PlaybackBootstrapTransport>;
  if (typeof payload.stream_url !== "string" || !payload.stream_url.trim()) {
    throw new Error("Atlas returned an invalid playback stream.");
  }

  return Object.freeze({
    streamUrl: validateStreamUrl(payload.stream_url)
  });
}
