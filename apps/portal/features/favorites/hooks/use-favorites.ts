"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";

import { loadFavorites, removeFavorite as requestFavoriteRemoval } from "../api/favorites";
import { createFavoritesState, type Favorite, type FavoritesState } from "../types/favorites";

export type UseFavoritesResult = Readonly<{
  state: FavoritesState;
  refresh: () => void;
  removeFavorite: (favoriteId: string) => Promise<boolean>;
  removingFavoriteId: string | null;
  mutationError: Error | null;
}>;

type FavoritesLoadResult = Readonly<{
  userId: string;
  data: readonly Favorite[] | null;
  error: Error | null;
}>;

function normalizeFavoritesError(value: unknown, fallback: string): Error {
  if (value instanceof Error) {
    return value;
  }

  return new Error(fallback);
}

export function useFavorites(): UseFavoritesResult {
  const { isAuthenticated, user } = useAuth();
  const currentUserId = user?.user_id ?? null;

  const [loadResult, setLoadResult] = useState<FavoritesLoadResult | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const [removingFavoriteId, setRemovingFavoriteId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<Error | null>(null);

  const refresh = useCallback((): void => {
    setLoadResult(null);
    setMutationError(null);
    setRequestVersion((currentVersion) => currentVersion + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    if (!isAuthenticated || !currentUserId) {
      return () => {
        controller.abort();
      };
    }

    void loadFavorites({
      expectedUserId: currentUserId,
      signal: controller.signal
    })
      .then((favorites) => {
        if (controller.signal.aborted) {
          return;
        }

        setLoadResult({
          userId: currentUserId,
          data: favorites,
          error: null
        });
      })
      .catch((requestError: unknown) => {
        if (
          controller.signal.aborted ||
          (requestError instanceof DOMException && requestError.name === "AbortError")
        ) {
          return;
        }

        setLoadResult({
          userId: currentUserId,
          data: null,
          error: normalizeFavoritesError(requestError, "Unable to load your Atlas favorites.")
        });
      });

    return () => {
      controller.abort();
    };
  }, [currentUserId, isAuthenticated, requestVersion]);

  const state = useMemo(() => {
    if (!currentUserId || loadResult?.userId !== currentUserId) {
      return createFavoritesState(null, null);
    }

    return createFavoritesState(loadResult.data, loadResult.error);
  }, [currentUserId, loadResult]);

  const removeFavorite = useCallback(
    async (favoriteId: string): Promise<boolean> => {
      if (!isAuthenticated || !currentUserId) {
        setMutationError(new Error("Atlas authentication session is unavailable."));
        return false;
      }

      setRemovingFavoriteId(favoriteId);
      setMutationError(null);

      try {
        const removed = await requestFavoriteRemoval(favoriteId, {
          expectedUserId: currentUserId
        });

        setLoadResult((current) => {
          if (current?.userId !== currentUserId || current.data === null) {
            return current;
          }

          return {
            userId: currentUserId,
            data: current.data.filter((favorite) => favorite.favoriteId !== removed.favoriteId),
            error: null
          };
        });

        return true;
      } catch (requestError: unknown) {
        setMutationError(
          normalizeFavoritesError(requestError, "Unable to remove this Atlas favorite.")
        );

        return false;
      } finally {
        setRemovingFavoriteId(null);
      }
    },
    [currentUserId, isAuthenticated]
  );

  return {
    state,
    refresh,
    removeFavorite,
    removingFavoriteId,
    mutationError
  };
}
