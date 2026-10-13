/** Opt-in, local console observations. Never log HLS URLs, headers or errors. */
type Event = "hls_error" | "fragment_loaded" | "fragment_buffered";
type Video = Pick<HTMLVideoElement, "currentTime" | "paused" | "readyState" | "buffered" | "error">;
type Options = Readonly<{
  enabled?: () => boolean;
  now?: () => number;
  write?: (value: string) => void;
}>;

function enabled(): boolean {
  try {
    return typeof window !== "undefined" &&
      window.localStorage.getItem("atlas.playback.diagnostics") === "1";
  } catch { return false; }
}
function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function label(value: unknown): string | null {
  return typeof value === "string" && /^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(value) ? value : null;
}

export function createPlaybackDiagnostics(video: Video, options: Options = {}) {
  const isEnabled = options.enabled ?? enabled;
  const now = options.now ?? Date.now;
  const write = options.write ?? ((value: string) => console.info(value));
  const last = new Map<Event, number>();
  let count = 0;
  return (event: Event, fields: Readonly<Record<string, unknown>> = {}): void => {
    try {
      if (!isEnabled() || count >= 200) return;
      const stamp = now();
      if (event !== "hls_error" && last.has(event) && stamp - last.get(event)! < 10_000) return;
      last.set(event, stamp);
      const buffered = [];
      for (let index = 0; index < Math.min(video.buffered.length, 8); index++) {
        buffered.push([number(video.buffered.start(index)), number(video.buffered.end(index))]);
      }
      const row = {
        time: new Date(stamp).toISOString(), event,
        position: number(video.currentTime), paused: video.paused,
        readyState: video.readyState, mediaErrorCode: number(video.error?.code), buffered,
        type: label(fields.type), details: label(fields.details),
        fatal: typeof fields.fatal === "boolean" ? fields.fatal : null,
        responseStatus: number(fields.responseStatus),
        fragmentSequence: number(fields.fragmentSequence),
        fragmentStart: number(fields.fragmentStart),
        fragmentDuration: number(fields.fragmentDuration),
      };
      write("ATLAS_HLS " + JSON.stringify(row));
      count++;
    } catch { /* Diagnostics must not interfere with playback or recovery. */ }
  };
}
