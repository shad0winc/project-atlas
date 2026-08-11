import {
  readFavorites,
  removeFavoriteRecord,
  type ReadFavoritesOptions,
  type RemoveFavoriteOptions
} from "../services/favorites";
import type { Favorite } from "../types/favorites";

export type LoadFavoritesOptions = ReadFavoritesOptions;
export type RemoveFavoriteRequestOptions = RemoveFavoriteOptions;

export async function loadFavorites(options: LoadFavoritesOptions): Promise<readonly Favorite[]> {
  return readFavorites(options);
}

export async function removeFavorite(
  favoriteId: string,
  options: RemoveFavoriteRequestOptions
): Promise<Favorite> {
  return removeFavoriteRecord(favoriteId, options);
}
