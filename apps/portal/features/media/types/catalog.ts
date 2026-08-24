export type MediaCatalogItem = Readonly<{
  provider: string;
  itemId: string;
  mediaType: string;
  title: string;
  year?: number;
  library?: string;
}>;

export type MediaCatalogPage = Readonly<{
  provider: string;
  page: number;
  pageSize: number;
  total: number;
  items: readonly MediaCatalogItem[];
}>;

export type CreateMediaCatalogItemInput = Readonly<{
  provider: string;
  itemId: string;
  mediaType: string;
  title: string;
  year?: number;
  library?: string;
}>;

export type CreateMediaCatalogPageInput = Readonly<{
  provider: string;
  page: number;
  pageSize: number;
  total: number;
  items: readonly CreateMediaCatalogItemInput[];
}>;

function normalizeRequiredText(value: string, label: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${label} must not be empty.`);
  }

  return normalized;
}

function normalizePositiveInteger(value: number, label: string): number {
  if (!Number.isInteger(value) || value < 1) {
    throw new Error(`${label} must be a positive integer.`);
  }

  return value;
}

export function createMediaCatalogItem(input: CreateMediaCatalogItemInput): MediaCatalogItem {
  const provider = normalizeRequiredText(input.provider, "catalog.provider").toLowerCase();

  const itemId = normalizeRequiredText(input.itemId, "catalog.itemId");

  const mediaType = normalizeRequiredText(input.mediaType, "catalog.mediaType").toLowerCase();

  const title = normalizeRequiredText(input.title, "catalog.title");

  let year: number | undefined;

  if (input.year !== undefined) {
    if (!Number.isInteger(input.year) || input.year < 1) {
      throw new Error("catalog.year must be a positive integer.");
    }

    year = input.year;
  }

  const library =
    input.library === undefined
      ? undefined
      : normalizeRequiredText(input.library, "catalog.library");

  return Object.freeze({
    provider,
    itemId,
    mediaType,
    title,
    ...(year === undefined ? {} : { year }),
    ...(library === undefined ? {} : { library })
  });
}

export function createMediaCatalogPage(input: CreateMediaCatalogPageInput): MediaCatalogPage {
  const provider = normalizeRequiredText(input.provider, "catalog.provider").toLowerCase();

  const page = normalizePositiveInteger(input.page, "catalog.page");

  const pageSize = normalizePositiveInteger(input.pageSize, "catalog.pageSize");

  if (!Number.isInteger(input.total) || input.total < 0) {
    throw new Error("catalog.total must be a nonnegative integer.");
  }

  const items = input.items.map(createMediaCatalogItem);

  if (items.some((item) => item.provider !== provider)) {
    throw new Error("Catalog item provider did not match the catalog provider.");
  }

  const identities = new Set(items.map((item) => `${item.provider}\u0000${item.itemId}`));

  if (identities.size !== items.length) {
    throw new Error("Media catalog identities must be unique within a page.");
  }

  if (items.length > pageSize) {
    throw new Error("Media catalog page exceeds pageSize.");
  }

  if (input.total < items.length) {
    throw new Error("Media catalog total cannot be smaller than the current page.");
  }

  return Object.freeze({
    provider,
    page,
    pageSize,
    total: input.total,
    items: Object.freeze(items)
  });
}
