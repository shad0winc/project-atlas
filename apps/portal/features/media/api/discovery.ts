import {
  readMediaDiscovery,
  searchMediaDiscovery,
  type ReadMediaDiscoveryOptions,
  type SearchMediaDiscoveryOptions
} from "../services/discovery";

import type { MediaDiscoveryPage } from "../types/discovery";

export async function loadMediaDiscovery(
  options: ReadMediaDiscoveryOptions
): Promise<MediaDiscoveryPage> {
  return readMediaDiscovery(options);
}

export async function loadMediaSearch(
  options: SearchMediaDiscoveryOptions
): Promise<MediaDiscoveryPage> {
  return searchMediaDiscovery(options);
}

export type { ReadMediaDiscoveryOptions, SearchMediaDiscoveryOptions };
