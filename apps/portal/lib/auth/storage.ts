import type { AtlasAuthSession } from "./types";

/**
 * Minimal session store used by the Portal authentication provider.
 *
 * Access tokens and user projections remain in process memory. On refresh the
 * Portal restores a validated session through the API-owned HttpOnly cookie.
 * Refresh credentials are never written to this store or browser storage.
 */
let activeSession: AtlasAuthSession | null = null;

export function readAtlasAuthSession(): AtlasAuthSession | null {
  return activeSession;
}

export function writeAtlasAuthSession(session: AtlasAuthSession): void {
  activeSession = session;
}

export function clearAtlasAuthSession(): void {
  activeSession = null;
}
