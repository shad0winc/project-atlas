import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import { normalizeMediaDiscoveryProviderId } from "../types/discovery";
import {
  createMediaSeriesDetail,
  type MediaSeriesDetail,
  type MediaSeriesSeason,
  type MediaSeriesStatus
} from "../types/series";

type MediaSeriesSeasonTransportResponse = Readonly<{
  season_number: number;
  name: string;
  episode_count: number;
  availability: string;
  requestability_known: boolean;
  request_eligible: boolean;
  air_date: string | null;
}>;

type MediaSeriesDetailTransportResponse = Readonly<{
  provider_media_id: string;
  title: string;
  year: number | null;
  overview: string | null;
  poster_path: string | null;
  status: string;
  in_production: boolean;
  is_ongoing: boolean;
  is_anime: boolean;
  availability: string;
  request_eligible: boolean;
  seasons: readonly MediaSeriesSeasonTransportResponse[];
}>;

export type ReadMediaSeriesDetailOptions = Readonly<{
  providerMediaId: string;
  signal?: AbortSignal;
}>;

function mapSeason(response: MediaSeriesSeasonTransportResponse): MediaSeriesSeason {
  return {
    seasonNumber: response.season_number,
    name: response.name,
    episodeCount: response.episode_count,
    availability: response.availability as MediaSeriesSeason["availability"],
    requestabilityKnown: response.requestability_known,
    requestEligible: response.request_eligible,
    ...(response.air_date === null ? {} : { airDate: response.air_date })
  };
}

function mapSeries(response: MediaSeriesDetailTransportResponse): MediaSeriesDetail {
  return createMediaSeriesDetail({
    providerMediaId: response.provider_media_id,
    title: response.title,
    ...(response.year === null ? {} : { year: response.year }),
    ...(response.overview === null ? {} : { overview: response.overview }),
    ...(response.poster_path === null ? {} : { posterPath: response.poster_path }),
    status: response.status as MediaSeriesStatus,
    inProduction: response.in_production,
    isOngoing: response.is_ongoing,
    isAnime: response.is_anime,
    availability: response.availability as MediaSeriesDetail["availability"],
    requestEligible: response.request_eligible,
    seasons: response.seasons.map(mapSeason)
  });
}

export async function readMediaSeriesDetail({
  providerMediaId,
  signal
}: ReadMediaSeriesDetailOptions): Promise<MediaSeriesDetail> {
  const normalizedProviderMediaId = normalizeMediaDiscoveryProviderId(providerMediaId);

  const response = await authenticatedAtlasApiRequest<MediaSeriesDetailTransportResponse>(
    `/media/tv/${encodeURIComponent(normalizedProviderMediaId)}`,
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  const detail = mapSeries(response);

  if (detail.providerMediaId !== normalizedProviderMediaId) {
    throw new Error("Media series detail identity did not match the requested title.");
  }

  return detail;
}
