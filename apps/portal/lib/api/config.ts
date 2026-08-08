/**
 * Portal-facing Atlas API configuration.
 *
 * Browser requests use the same public origin. Caddy owns `/api/*` routing,
 * so the Portal does not need to expose an API hostname to browser code.
 */

export const ATLAS_API_PREFIX = "/api/v1";

/**
 * Default maximum duration for a Portal request to the Atlas API.
 *
 * Individual requests may override this value when a different operational
 * requirement is justified.
 */
export const ATLAS_API_DEFAULT_TIMEOUT_MS = 10_000;

export function atlasApiPath(path: string): string {
  const normalizedPath = path.trim();

  if (!normalizedPath) {
    throw new Error("Atlas API path cannot be empty.");
  }

  if (!normalizedPath.startsWith("/")) {
    throw new Error("Atlas API path must begin with '/'.");
  }

  return `${ATLAS_API_PREFIX}${normalizedPath}`;
}
