/** Preserve a bounded server retry hint; never invent an earlier retry. */
export function parseAtlasRetryAfter(value: string | null, now = Date.now()): number | null {
  if (value === null || !value.trim()) return null;
  const text = value.trim();
  const seconds = /^\d+$/.test(text)
    ? Number(text)
    : Math.ceil((Date.parse(text) - now) / 1000);
  return Number.isFinite(seconds) && seconds >= 0 && seconds <= 3600 ? seconds : null;
}
