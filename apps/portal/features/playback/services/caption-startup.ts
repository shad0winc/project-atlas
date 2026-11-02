import type { LoaderConfig } from "hls.js";

// A cold embedded subtitle can take longer than the normal fragment first-byte
// limit to extract. One bounded request lets Jellyfin finish that preparation.
export const CAPTION_STARTUP_MS = 120_000;

export function captionStartupPolicy(normal: LoaderConfig): LoaderConfig {
  return {
    ...normal,
    maxTimeToFirstByteMs: CAPTION_STARTUP_MS,
    maxLoadTimeMs: CAPTION_STARTUP_MS,
    timeoutRetry: null,
    errorRetry: null
  };
}
