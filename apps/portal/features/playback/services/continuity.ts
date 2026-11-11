// Browser-local continuity is separate from server viewing/completion evidence.
const RESUME_PREFIX = "atlas:resume:v1:";
type ResumeDetails = Readonly<{ title: string; duration?: number; episode?: boolean }>;
export type SavedResume = ResumeDetails & Readonly<{
  provider: string; itemId: string; position: number; updatedAt: number;
}>;

export type ResumeStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
export function resumeKey(userId: string | undefined, provider: string, itemId: string, canSeek: boolean): string | null {
  return userId && canSeek ? `${RESUME_PREFIX}${JSON.stringify([userId, provider, itemId])}` : null;
}
export function readResume(storage: ResumeStorage, key: string | null): number | null {
  if (!key) return null;
  try {
    const row = JSON.parse(storage.getItem(key) ?? "null");
    return row && typeof row.position === "number" && Number.isFinite(row.position) && row.position > 0 ? row.position : null;
  } catch { return null; }
}
export function writeResume(storage: ResumeStorage, key: string | null, position: number, ended = false, details?: ResumeDetails): void {
  if (!key) return;
  try {
    if (ended || position === 0) storage.removeItem(key);
    else if (Number.isFinite(position) && position > 0) storage.setItem(key, JSON.stringify({ position, ...details, ...(details ? { updatedAt: Date.now() } : {}) }));
  } catch { /* Storage may be unavailable; playback must still work. */ }
}

export function listSavedResumes(storage: Pick<Storage, "length" | "key" | "getItem">, userId: string): SavedResume[] {
  const items: SavedResume[] = [];
  for (let index = 0; index < storage.length; index++) {
    const key = storage.key(index);
    if (!key?.startsWith(RESUME_PREFIX)) continue;
    try {
      const identity: unknown = JSON.parse(key.slice(RESUME_PREFIX.length));
      if (!Array.isArray(identity) || identity.length !== 3 || identity[0] !== userId) continue;
      const [, provider, itemId] = identity;
      if (typeof provider !== "string" || !provider || typeof itemId !== "string" || !itemId) continue;
      const row = JSON.parse(storage.getItem(key) ?? "null");
      if (!row || typeof row.title !== "string" || !row.title.trim() ||
          !Number.isFinite(row.position) || row.position <= 0 || !Number.isFinite(row.updatedAt)) continue;
      const duration = Number.isFinite(row.duration) && row.duration > 0 ? row.duration : undefined;
      items.push({ provider, itemId, title: row.title, position: row.position, duration,
        updatedAt: row.updatedAt, episode: row.episode === true });
    } catch { /* Ignore invalid storage rows. */ }
  }
  return items.sort((left, right) => right.updatedAt - left.updatedAt);
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
