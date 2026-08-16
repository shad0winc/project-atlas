import {
  createFavoriteRecord,
  readFavorites,
  removeFavoriteRecord,
  type CreateFavoriteOptions,
  type FavoriteCreateInput,
  type ReadFavoritesOptions,
  type RemoveFavoriteOptions
} from "../services/favorites";
import type { Favorite } from "../types/favorites";

export type AddFavoriteOptions = CreateFavoriteOptions;
export type AddFavoriteInput = FavoriteCreateInput;
export type LoadFavoritesOptions = ReadFavoritesOptions;
export type RemoveFavoriteRequestOptions = RemoveFavoriteOptions;

export async function loadFavorites(options: LoadFavoritesOptions): Promise<readonly Favorite[]> {
  return readFavorites(options);
}

export async function addFavorite(
  input: AddFavoriteInput,
  options: AddFavoriteOptions
): Promise<Favorite> {
  return createFavoriteRecord(input, options);
}

export async function removeFavorite(
  favoriteId: string,
  options: RemoveFavoriteRequestOptions
): Promise<Favorite> {
  return removeFavoriteRecord(favoriteId, options);
}
