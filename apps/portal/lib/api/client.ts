/**
 * Public Atlas Portal API client.
 *
 * A single HTTP attempt is implemented by request.ts. Retry policy,
 * authentication refresh, and other orchestration belong at this boundary.
 */

import { performAtlasApiRequest, type AtlasApiRequestOptions } from "./request";

export type { AtlasApiRequestOptions } from "./request";

export function atlasApiRequest<T>(path: string, options: AtlasApiRequestOptions = {}): Promise<T> {
  return performAtlasApiRequest<T>(path, options);
}
