import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import { createMediaCatalogPage, type MediaCatalogPage } from "../types/catalog";

type MediaCatalogItemTransportResponse = Readonly<{
  provider: string;
  item_id: string;
  media_type: string;
  title: string;
  year: number | null;
  library: string | null;
}>;

type MediaCatalogTransportResponse = Readonly<{
  provider: string;
  page: number;
  page_size: number;
  total: number;
  items: readonly MediaCatalogItemTransportResponse[];
}>;

export type ReadMediaCatalogOptions = Readonly<{
  page?: number;
  pageSize?: number;
  signal?: AbortSignal;
}>;

export async function readMediaCatalog({
  page = 1,
  pageSize = 24,
  signal
}: ReadMediaCatalogOptions = {}): Promise<MediaCatalogPage> {
  if (!Number.isInteger(page) || page < 1) {
    throw new Error("catalog.page must be a positive integer.");
  }

  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
    throw new Error("catalog.pageSize must be between 1 and 100.");
  }

  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize)
  });

  const response = await authenticatedAtlasApiRequest<MediaCatalogTransportResponse>(
    `/media/catalog?${query.toString()}`,
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return createMediaCatalogPage({
    provider: response.provider,
    page: response.page,
    pageSize: response.page_size,
    total: response.total,
    items: response.items.map((item) => ({
      provider: item.provider,
      itemId: item.item_id,
      mediaType: item.media_type,
      title: item.title,
      ...(item.year === null ? {} : { year: item.year }),
      ...(item.library === null ? {} : { library: item.library })
    }))
  });
}
