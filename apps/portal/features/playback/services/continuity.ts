// Browser-local continuity is separate from server viewing/completion evidence.
export type ResumeStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
export function resumeKey(userId: string | undefined, provider: string, itemId: string, canSeek: boolean): string | null {
  return userId && canSeek ? `atlas:resume:v1:${JSON.stringify([userId, provider, itemId])}` : null;
}
export function readResume(storage: ResumeStorage, key: string | null): number | null {
  if (!key) return null;
  try {
    const row = JSON.parse(storage.getItem(key) ?? "null");
    return row && typeof row.position === "number" && Number.isFinite(row.position) && row.position > 0 ? row.position : null;
  } catch { return null; }
}
export function writeResume(storage: ResumeStorage, key: string | null, position: number, ended = false): void {
  if (!key) return;
  try {
    if (ended || position === 0) storage.removeItem(key);
    else if (Number.isFinite(position) && position > 0) storage.setItem(key, JSON.stringify({ position }));
  } catch { /* Storage may be unavailable; playback must still work. */ }
}

export type ContinuityVideo = Pick<HTMLVideoElement, "currentTime" | "duration" | "seekable" | "readyState" | "play">;
export async function restoreContinuity(
  video: ContinuityVideo,
  position: number | null,
  shouldPlay: boolean
): Promise<{ restored: boolean; blocked: boolean }> {
  if (video.readyState < 2) return { restored: false, blocked: false };
  if (position !== null && Number.isFinite(position) && position > 0) {
    // Do not clear the saved position before the HLS seekable window is ready.
    const target = Number.isFinite(video.duration) ? Math.min(position, Math.max(0, video.duration - 1)) : position;
    let seekable = false;
    for (let i = 0; i < video.seekable.length; i++) {
      if (target >= video.seekable.start(i) && target <= video.seekable.end(i)) seekable = true;
    }
    if (!seekable) return { restored: false, blocked: false };
    try { video.currentTime = target; } catch { return { restored: false, blocked: false }; }
  }
  if (shouldPlay) {
    try { await video.play(); } catch { return { restored: true, blocked: true }; }
  }
  return { restored: true, blocked: false };
}
