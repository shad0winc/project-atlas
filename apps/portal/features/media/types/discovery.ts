export const MEDIA_DISCOVERY_MEDIA_TYPES = ["movie", "tv"] as const;

export type MediaDiscoveryMediaType = (typeof MEDIA_DISCOVERY_MEDIA_TYPES)[number];

export const MEDIA_DISCOVERY_AVAILABILITIES = [
  "not_tracked",
  "unknown",
  "pending",
  "processing",
  "partially_available",
  "available",
  "blocklisted",
  "deleted"
] as const;

export type MediaDiscoveryAvailability = (typeof MEDIA_DISCOVERY_AVAILABILITIES)[number];

export type MediaDiscoveryItem = Readonly<{
  providerMediaId: string;
  mediaType: MediaDiscoveryMediaType;
  title: string;
  year?: number;
  overview?: string;
  posterPath?: string;
  availability: MediaDiscoveryAvailability;
  requestEligible: boolean;
}>;

export type MediaDiscoveryPage = Readonly<{
  items: readonly MediaDiscoveryItem[];
  page: number;
  totalPages: number;
  nextPage: number | null;
}>;

export type CreateMediaDiscoveryPageInput = Readonly<{
  items: readonly MediaDiscoveryItem[];
  page: number;
  totalPages: number;
}>;

function normalizeRequiredText(value: string, fieldName: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }

  return normalized;
}

function normalizeOptionalText(value: string | undefined): string | undefined {
  const normalized = value?.trim();

  return normalized ? normalized : undefined;
}

export function normalizeMediaDiscoveryProviderId(value: string): string {
  const normalized = normalizeRequiredText(value, "providerMediaId");

  if (!/^[0-9]+$/.test(normalized) || Number(normalized) <= 0) {
    throw new Error("providerMediaId must be a positive numeric TMDB identifier.");
  }

  return normalized;
}

export function normalizeMediaDiscoveryType(value: string): MediaDiscoveryMediaType {
  const normalized = value.trim().toLowerCase();

  if (!MEDIA_DISCOVERY_MEDIA_TYPES.includes(normalized as MediaDiscoveryMediaType)) {
    throw new Error("mediaType must be movie or tv.");
  }

  return normalized as MediaDiscoveryMediaType;
}

export function normalizeMediaDiscoveryAvailability(value: string): MediaDiscoveryAvailability {
  const normalized = value.trim().toLowerCase().replace(/[- ]/g, "_");

  if (!MEDIA_DISCOVERY_AVAILABILITIES.includes(normalized as MediaDiscoveryAvailability)) {
    throw new Error("availability is unsupported.");
  }

  return normalized as MediaDiscoveryAvailability;
}

export function normalizeMediaDiscoveryQuery(value: string): string {
  const normalized = normalizeRequiredText(value, "query");

  if (normalized.length > 200) {
    throw new Error("query must contain at most 200 characters.");
  }

  return normalized;
}

export function normalizeMediaDiscoveryPageNumber(value: number): number {
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error("page must be a positive integer.");
  }

  return value;
}

function normalizeYear(value: number | undefined): number | undefined {
  if (value === undefined) {
    return undefined;
  }

  const maximumYear = new Date().getUTCFullYear() + 10;

  if (!Number.isInteger(value) || value < 1888 || value > maximumYear) {
    throw new Error(`year must be between 1888 and ${maximumYear}.`);
  }

  return value;
}

function normalizePosterPath(value: string | undefined): string | undefined {
  const normalized = normalizeOptionalText(value);

  if (normalized === undefined) {
    return undefined;
  }

  if (!normalized.startsWith("/")) {
    throw new Error("posterPath must be a relative provider path.");
  }

  return normalized;
}

export function createMediaDiscoveryItem(item: MediaDiscoveryItem): MediaDiscoveryItem {
  const providerMediaId = normalizeMediaDiscoveryProviderId(item.providerMediaId);
  const mediaType = normalizeMediaDiscoveryType(item.mediaType);
  const title = normalizeRequiredText(item.title, "title");
  const year = normalizeYear(item.year);
  const overview = normalizeOptionalText(item.overview);
  const posterPath = normalizePosterPath(item.posterPath);
  const availability = normalizeMediaDiscoveryAvailability(item.availability);

  if (typeof item.requestEligible !== "boolean") {
    throw new Error("requestEligible must be boolean.");
  }

  const expectedEligibility = availability === "not_tracked";

  if (item.requestEligible !== expectedEligibility) {
    throw new Error("requestEligible does not match the discovery availability state.");
  }

  return {
    providerMediaId,
    mediaType,
    title,
    ...(year === undefined ? {} : { year }),
    ...(overview === undefined ? {} : { overview }),
    ...(posterPath === undefined ? {} : { posterPath }),
    availability,
    requestEligible: expectedEligibility
  };
}

export function createMediaDiscoveryPage(input: CreateMediaDiscoveryPageInput): MediaDiscoveryPage {
  const items = input.items.map(createMediaDiscoveryItem);
  const page = normalizeMediaDiscoveryPageNumber(input.page);

  if (!Number.isInteger(input.totalPages) || input.totalPages < 0) {
    throw new Error("totalPages must be a nonnegative integer.");
  }

  const totalPages = input.totalPages;

  if (items.length > 0 && totalPages === 0) {
    throw new Error("totalPages cannot be zero when discovery items are present.");
  }

  if (totalPages > 0 && page > totalPages) {
    throw new Error("page cannot exceed totalPages.");
  }

  const identities = new Set(items.map((item) => `${item.mediaType}:${item.providerMediaId}`));

  if (identities.size !== items.length) {
    throw new Error("Media discovery identities must be unique within a page.");
  }

  const nextPage = totalPages > 0 && page < totalPages ? page + 1 : null;

  return {
    items,
    page,
    totalPages,
    nextPage
  };
}

export function mediaDiscoveryAvailabilityLabel(availability: MediaDiscoveryAvailability): string {
  switch (availability) {
    case "not_tracked":
      return "Not tracked";
    case "unknown":
      return "Unknown";
    case "pending":
      return "Pending";
    case "processing":
      return "Processing";
    case "partially_available":
      return "Partially available";
    case "available":
      return "Available";
    case "blocklisted":
      return "Blocklisted";
    case "deleted":
      return "Deleted";
  }
}
