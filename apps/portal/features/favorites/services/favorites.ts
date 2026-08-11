import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createFavorite,
  createFavoriteCollection,
  normalizeFavoriteId,
  normalizeFavoriteUserId,
  type Favorite
} from "../types/favorites";

export type ReadFavoritesOptions = Readonly<{
  expectedUserId: string;
  signal?: AbortSignal;
}>;

export type RemoveFavoriteOptions = Readonly<{
  expectedUserId: string;
  signal?: AbortSignal;
}>;

type FavoriteTransportResponse = Readonly<{
  schema_version: number;
  favorite_id: string;
  user_id: string;
  provider: string;
  item_id: string;
  media_type: string;
  title: string | null;
  metadata: Readonly<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}>;

type FavoriteListTransportResponse = Readonly<{
  favorites: readonly FavoriteTransportResponse[];
}>;

function mapFavorite(response: FavoriteTransportResponse): Favorite {
  return createFavorite({
    schemaVersion: response.schema_version,
    favoriteId: response.favorite_id,
    userId: response.user_id,
    provider: response.provider,
    itemId: response.item_id,
    mediaType: response.media_type,
    ...(response.title === null ? {} : { title: response.title }),
    metadata: response.metadata,
    createdAt: response.created_at,
    updatedAt: response.updated_at
  });
}

export async function readFavorites({
  expectedUserId,
  signal
}: ReadFavoritesOptions): Promise<readonly Favorite[]> {
  const normalizedUserId = normalizeFavoriteUserId(expectedUserId);

  const response = await authenticatedAtlasApiRequest<FavoriteListTransportResponse>("/favorites", {
    method: "GET",
    cache: "no-store",
    signal
  });

  return createFavoriteCollection(response.favorites.map(mapFavorite), normalizedUserId);
}

export async function removeFavoriteRecord(
  favoriteId: string,
  { expectedUserId, signal }: RemoveFavoriteOptions
): Promise<Favorite> {
  const normalizedFavoriteId = normalizeFavoriteId(favoriteId);
  const normalizedUserId = normalizeFavoriteUserId(expectedUserId);

  const response = await authenticatedAtlasApiRequest<FavoriteTransportResponse>(
    `/favorites/${encodeURIComponent(normalizedFavoriteId)}`,
    {
      method: "DELETE",
      cache: "no-store",
      signal
    }
  );

  const removed = mapFavorite(response);

  if (removed.favoriteId !== normalizedFavoriteId) {
    throw new Error("Favorites removal response did not match the requested Favorite.");
  }

  if (removed.userId !== normalizedUserId) {
    throw new Error("Favorites removal response crossed the authenticated-user boundary.");
  }

  return removed;
}
