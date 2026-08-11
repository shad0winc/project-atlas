import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createMediaDiscoveryItem,
  createMediaDiscoveryPage,
  normalizeMediaDiscoveryPageNumber,
  normalizeMediaDiscoveryQuery,
  normalizeMediaDiscoveryType,
  type MediaDiscoveryItem,
  type MediaDiscoveryMediaType,
  type MediaDiscoveryPage
} from "../types/discovery";

type MediaDiscoveryItemTransportResponse = Readonly<{
  provider_media_id: string;
  media_type: string;
  title: string;
  year: number | null;
  overview: string | null;
  poster_path: string | null;
  availability: string;
  request_eligible: boolean;
}>;

type MediaDiscoveryPageTransportResponse = Readonly<{
  items: readonly MediaDiscoveryItemTransportResponse[];
  page: number;
  total_pages: number;
  next_page: number | null;
}>;

export type ReadMediaDiscoveryOptions = Readonly<{
  mediaType: MediaDiscoveryMediaType;
  page?: number;
  signal?: AbortSignal;
}>;

export type SearchMediaDiscoveryOptions = Readonly<{
  query: string;
  page?: number;
  signal?: AbortSignal;
}>;

function mapDiscoveryItem(response: MediaDiscoveryItemTransportResponse): MediaDiscoveryItem {
  return createMediaDiscoveryItem({
    providerMediaId: response.provider_media_id,
    mediaType: response.media_type as MediaDiscoveryMediaType,
    title: response.title,
    ...(response.year === null ? {} : { year: response.year }),
    ...(response.overview === null ? {} : { overview: response.overview }),
    ...(response.poster_path === null ? {} : { posterPath: response.poster_path }),
    availability: response.availability as MediaDiscoveryItem["availability"],
    requestEligible: response.request_eligible
  });
}

function mapDiscoveryPage(response: MediaDiscoveryPageTransportResponse): MediaDiscoveryPage {
  const page = createMediaDiscoveryPage({
    items: response.items.map(mapDiscoveryItem),
    page: response.page,
    totalPages: response.total_pages
  });

  if (response.next_page !== page.nextPage) {
    throw new Error("Media discovery pagination did not match the Atlas API contract.");
  }

  return page;
}

export async function readMediaDiscovery({
  mediaType,
  page = 1,
  signal
}: ReadMediaDiscoveryOptions): Promise<MediaDiscoveryPage> {
  const normalizedMediaType = normalizeMediaDiscoveryType(mediaType);
  const normalizedPage = normalizeMediaDiscoveryPageNumber(page);

  const query = new URLSearchParams({
    media_type: normalizedMediaType,
    page: String(normalizedPage)
  });

  const response = await authenticatedAtlasApiRequest<MediaDiscoveryPageTransportResponse>(
    `/media/discover?${query.toString()}`,
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return mapDiscoveryPage(response);
}

export async function searchMediaDiscovery({
  query,
  page = 1,
  signal
}: SearchMediaDiscoveryOptions): Promise<MediaDiscoveryPage> {
  const normalizedQuery = normalizeMediaDiscoveryQuery(query);
  const normalizedPage = normalizeMediaDiscoveryPageNumber(page);

  const search = new URLSearchParams({
    query: normalizedQuery,
    page: String(normalizedPage)
  });

  const response = await authenticatedAtlasApiRequest<MediaDiscoveryPageTransportResponse>(
    `/media/search?${search.toString()}`,
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return mapDiscoveryPage(response);
}
