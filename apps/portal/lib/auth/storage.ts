import type { AtlasAuthSession } from "./types";

/**
 * Minimal session store used by the Portal authentication provider.
 *
 * Tokens intentionally remain in process memory. A browser refresh therefore
 * ends the Portal session. Persistent browser storage is deferred until Atlas
 * supports a server-managed cookie or another hardened session mechanism.
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
