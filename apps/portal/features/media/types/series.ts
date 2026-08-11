import {
  normalizeMediaDiscoveryAvailability,
  normalizeMediaDiscoveryProviderId,
  type MediaDiscoveryAvailability
} from "./discovery";

export const MEDIA_SERIES_STATUSES = [
  "returning",
  "planned",
  "in_production",
  "ended",
  "cancelled",
  "pilot",
  "unknown"
] as const;

export type MediaSeriesStatus = (typeof MEDIA_SERIES_STATUSES)[number];

export type MediaSeriesSeason = Readonly<{
  seasonNumber: number;
  name: string;
  episodeCount: number;
  availability: MediaDiscoveryAvailability;
  requestabilityKnown: boolean;
  requestEligible: boolean;
  airDate?: string;
}>;

export type MediaSeriesDetail = Readonly<{
  providerMediaId: string;
  title: string;
  year?: number;
  overview?: string;
  posterPath?: string;
  status: MediaSeriesStatus;
  inProduction: boolean;
  isOngoing: boolean;
  isAnime: boolean;
  availability: MediaDiscoveryAvailability;
  requestEligible: boolean;
  seasons: readonly MediaSeriesSeason[];
}>;

export type MediaSeriesRequestType = "tv" | "anime_tv";

function requiredText(value: string, fieldName: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }

  return normalized;
}

function optionalText(value: string | undefined): string | undefined {
  const normalized = value?.trim();

  return normalized ? normalized : undefined;
}

function normalizeYear(value: number | undefined): number | undefined {
  if (value === undefined) {
    return undefined;
  }

  const maximumYear = new Date().getUTCFullYear() + 10;

  if (!Number.isInteger(value) || value < 1888 || value > maximumYear) {
    throw new Error(`series.year must be between 1888 and ${maximumYear}.`);
  }

  return value;
}

function normalizePosterPath(value: string | undefined): string | undefined {
  const normalized = optionalText(value);

  if (normalized === undefined) {
    return undefined;
  }

  if (!normalized.startsWith("/")) {
    throw new Error("series.posterPath must be a relative provider path.");
  }

  return normalized;
}

function normalizeStatus(value: string): MediaSeriesStatus {
  const normalized = requiredText(value, "series.status").toLowerCase().replace(/[- ]/g, "_");

  if (!MEDIA_SERIES_STATUSES.includes(normalized as MediaSeriesStatus)) {
    throw new Error("series.status is unsupported.");
  }

  return normalized as MediaSeriesStatus;
}

function normalizePositiveInteger(value: number, fieldName: string): number {
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`${fieldName} must be a positive integer.`);
  }

  return value;
}

function normalizeNonnegativeInteger(value: number, fieldName: string): number {
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`${fieldName} must be a nonnegative integer.`);
  }

  return value;
}

function normalizeBoolean(value: boolean, fieldName: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`${fieldName} must be boolean.`);
  }

  return value;
}

function normalizeAirDate(value: string | undefined): string | undefined {
  const normalized = optionalText(value);

  if (normalized === undefined) {
    return undefined;
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    throw new Error("season.airDate must use YYYY-MM-DD.");
  }

  const parsed = new Date(`${normalized}T00:00:00Z`);

  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== normalized) {
    throw new Error("season.airDate must be a valid calendar date.");
  }

  return normalized;
}

export function createMediaSeriesSeason(season: MediaSeriesSeason): MediaSeriesSeason {
  const seasonNumber = normalizePositiveInteger(season.seasonNumber, "season.seasonNumber");
  const name = requiredText(season.name, "season.name");
  const episodeCount = normalizeNonnegativeInteger(season.episodeCount, "season.episodeCount");
  const availability = normalizeMediaDiscoveryAvailability(season.availability);
  const requestabilityKnown = normalizeBoolean(
    season.requestabilityKnown,
    "season.requestabilityKnown"
  );
  const requestEligible = normalizeBoolean(season.requestEligible, "season.requestEligible");
  const airDate = normalizeAirDate(season.airDate);

  if (!requestabilityKnown && requestEligible) {
    throw new Error("season.requestEligible cannot be true when requestability is unknown.");
  }

  if (
    requestEligible &&
    availability !== "not_tracked" &&
    availability !== "unknown" &&
    availability !== "deleted"
  ) {
    throw new Error("season.requestEligible conflicts with the season availability state.");
  }

  return Object.freeze({
    seasonNumber,
    name,
    episodeCount,
    availability,
    requestabilityKnown,
    requestEligible,
    ...(airDate === undefined ? {} : { airDate })
  });
}

export function createMediaSeriesDetail(detail: MediaSeriesDetail): MediaSeriesDetail {
  const providerMediaId = normalizeMediaDiscoveryProviderId(detail.providerMediaId);
  const title = requiredText(detail.title, "series.title");
  const year = normalizeYear(detail.year);
  const overview = optionalText(detail.overview);
  const posterPath = normalizePosterPath(detail.posterPath);
  const status = normalizeStatus(detail.status);
  const inProduction = normalizeBoolean(detail.inProduction, "series.inProduction");
  const isAnime = normalizeBoolean(detail.isAnime, "series.isAnime");
  const availability = normalizeMediaDiscoveryAvailability(detail.availability);
  const requestEligible = normalizeBoolean(detail.requestEligible, "series.requestEligible");
  const seasons = detail.seasons.map(createMediaSeriesSeason).sort((left, right) => {
    return left.seasonNumber - right.seasonNumber;
  });

  const seasonNumbers = new Set(seasons.map((season) => season.seasonNumber));

  if (seasonNumbers.size !== seasons.length) {
    throw new Error("series.seasons must use unique season numbers.");
  }

  const expectedRequestEligible = availability === "not_tracked";

  if (requestEligible !== expectedRequestEligible) {
    throw new Error("series.requestEligible does not match the series availability state.");
  }

  const expectedOngoing =
    inProduction ||
    status === "returning" ||
    status === "planned" ||
    status === "in_production" ||
    status === "pilot";

  if (detail.isOngoing !== expectedOngoing) {
    throw new Error("series.isOngoing does not match the series lifecycle state.");
  }

  return Object.freeze({
    providerMediaId,
    title,
    ...(year === undefined ? {} : { year }),
    ...(overview === undefined ? {} : { overview }),
    ...(posterPath === undefined ? {} : { posterPath }),
    status,
    inProduction,
    isOngoing: expectedOngoing,
    isAnime,
    availability,
    requestEligible: expectedRequestEligible,
    seasons: Object.freeze(seasons)
  });
}

export function mediaSeriesRequestType(detail: MediaSeriesDetail): MediaSeriesRequestType {
  return detail.isAnime ? "anime_tv" : "tv";
}
