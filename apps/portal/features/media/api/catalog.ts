import { readMediaCatalog, type ReadMediaCatalogOptions } from "../services/catalog";

import type { MediaCatalogPage } from "../types/catalog";

export type LoadMediaCatalogOptions = ReadMediaCatalogOptions;

export async function loadMediaCatalog(
  options: LoadMediaCatalogOptions = {}
): Promise<MediaCatalogPage> {
  return readMediaCatalog(options);
}
