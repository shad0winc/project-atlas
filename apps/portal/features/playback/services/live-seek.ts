const LIVE_BUFFER_SECONDS = 7;
const WINDOW_START_MARGIN = 0.25;

type LiveSeekVideo = Pick<HTMLVideoElement, "buffered" | "seekable">;

// Clamp user seeks only. Normal playback and user pauses are left alone.
export function safeLiveSeekPosition(video: LiveSeekVideo, requested: number): number | null {
  if (!Number.isFinite(requested)) return null;
  let closest: number | null = null;
  let distance = Infinity;
  for (let i = 0; i < video.buffered.length; i++) {
    for (let j = 0; j < video.seekable.length; j++) {
      const start = Math.max(video.buffered.start(i), video.seekable.start(j));
      const end = Math.min(video.buffered.end(i), video.seekable.end(j));
      if (!Number.isFinite(start) || !Number.isFinite(end)) continue;
      const earliest = Math.max(LIVE_BUFFER_SECONDS, start + WINDOW_START_MARGIN);
      const latest = end - LIVE_BUFFER_SECONDS;
      if (earliest > latest) continue;
      const candidate = Math.max(earliest, Math.min(requested, latest));
      const candidateDistance = Math.abs(requested - candidate);
      if (candidateDistance < distance) {
        closest = candidate;
        distance = candidateDistance;
      }
    }
  }
  return closest;
}
