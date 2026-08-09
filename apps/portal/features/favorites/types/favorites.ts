export type FavoriteMetadata = Readonly<Record<string, unknown>>;

export type Favorite = Readonly<{
  schemaVersion: number;
  favoriteId: string;
  userId: string;
  provider: string;
  itemId: string;
  mediaType: string;
  title?: string;
  metadata: FavoriteMetadata;
  createdAt: string;
  updatedAt: string;
}>;

export type FavoritesLoadingState = Readonly<{
  status: "loading";
}>;

export type FavoritesReadyState = Readonly<{
  status: "ready";
  data: readonly Favorite[];
}>;

export type FavoritesErrorState = Readonly<{
  status: "error";
  error: Error;
}>;

export type FavoritesState = FavoritesLoadingState | FavoritesReadyState | FavoritesErrorState;

const FAVORITE_ID_PATTERN = /^fav_[a-f0-9]{32}$/;
const USER_ID_PATTERN = /^usr_[a-f0-9]{32}$/;

function normalizeRequiredText(value: string, fieldName: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${fieldName} must not be empty.`);
  }

  return normalized;
}

function normalizeIdentity(value: string, fieldName: string, pattern: RegExp): string {
  const normalized = normalizeRequiredText(value, fieldName).toLowerCase();

  if (!pattern.test(normalized)) {
    throw new Error(`${fieldName} is invalid.`);
  }

  return normalized;
}

function normalizeTimestamp(value: string, fieldName: string): string {
  const normalized = normalizeRequiredText(value, fieldName);
  const timestamp = new Date(normalized);

  if (Number.isNaN(timestamp.getTime())) {
    throw new Error(`${fieldName} must be a valid timestamp.`);
  }

  return timestamp.toISOString();
}

function normalizeOptionalText(value: string | undefined): string | undefined {
  const normalized = value?.trim();

  return normalized ? normalized : undefined;
}

function normalizeSchemaVersion(value: number): number {
  if (!Number.isInteger(value) || value < 1) {
    throw new Error("favorite.schemaVersion must be a positive integer.");
  }

  return value;
}

function normalizeMetadata(metadata: FavoriteMetadata): FavoriteMetadata {
  if (metadata === null || typeof metadata !== "object" || Array.isArray(metadata)) {
    throw new Error("favorite.metadata must be an object.");
  }

  return Object.freeze({
    ...metadata
  });
}

export function normalizeFavoriteId(value: string): string {
  return normalizeIdentity(value, "favorite.favoriteId", FAVORITE_ID_PATTERN);
}

export function normalizeFavoriteUserId(value: string): string {
  return normalizeIdentity(value, "favorite.userId", USER_ID_PATTERN);
}

export function createFavorite(favorite: Favorite): Favorite {
  const createdAt = normalizeTimestamp(favorite.createdAt, "favorite.createdAt");
  const updatedAt = normalizeTimestamp(favorite.updatedAt, "favorite.updatedAt");
  const title = normalizeOptionalText(favorite.title);

  return Object.freeze({
    schemaVersion: normalizeSchemaVersion(favorite.schemaVersion),
    favoriteId: normalizeFavoriteId(favorite.favoriteId),
    userId: normalizeFavoriteUserId(favorite.userId),
    provider: normalizeRequiredText(favorite.provider, "favorite.provider").toLowerCase(),
    itemId: normalizeRequiredText(favorite.itemId, "favorite.itemId"),
    mediaType: normalizeRequiredText(favorite.mediaType, "favorite.mediaType").toLowerCase(),
    ...(title === undefined ? {} : { title }),
    metadata: normalizeMetadata(favorite.metadata),
    createdAt,
    updatedAt
  });
}

export function createFavoriteCollection(
  favorites: readonly Favorite[],
  expectedUserId?: string
): readonly Favorite[] {
  const normalized = favorites.map(createFavorite);

  const favoriteIds = new Set(normalized.map((favorite) => favorite.favoriteId));

  if (favoriteIds.size !== normalized.length) {
    throw new Error("Favorite IDs must be unique.");
  }

  const mediaIdentities = new Set(
    normalized.map(
      (favorite) => `${favorite.userId}\u0000${favorite.provider}\u0000${favorite.itemId}`
    )
  );

  if (mediaIdentities.size !== normalized.length) {
    throw new Error("Favorite media identities must be unique.");
  }

  const ownerUserId =
    expectedUserId === undefined ? normalized[0]?.userId : normalizeFavoriteUserId(expectedUserId);

  if (ownerUserId && normalized.some((favorite) => favorite.userId !== ownerUserId)) {
    throw new Error("Favorites response crossed the authenticated-user boundary.");
  }

  return Object.freeze(normalized);
}

export function createFavoritesState(
  data: readonly Favorite[] | null,
  error: Error | null
): FavoritesState {
  if (error) {
    return {
      status: "error",
      error
    };
  }

  if (data !== null) {
    return {
      status: "ready",
      data
    };
  }

  return {
    status: "loading"
  };
}
