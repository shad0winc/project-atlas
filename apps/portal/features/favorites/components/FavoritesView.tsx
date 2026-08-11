"use client";

import { useCallback, useEffect, useState } from "react";

import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";

import { useFavorites } from "../hooks/use-favorites";
import type { Favorite, FavoritesState } from "../types/favorites";

export type FavoritesContentProps = Readonly<{
  state: FavoritesState;
  canRemove: boolean;
  pendingRemovalId: string | null;
  removingFavoriteId: string | null;
  mutationError: Error | null;
  onRetry: () => void;
  onBeginRemoval: (favoriteId: string) => void;
  onCancelRemoval: () => void;
  onConfirmRemoval: (favoriteId: string) => Promise<void> | void;
}>;

type FavoritesViewProps = Readonly<{
  onRefreshStateChange?: (refresh: () => void, isBusy: boolean) => void;
}>;

function displayToken(value: string): string {
  return value
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function favoriteTitle(favorite: Favorite): string {
  return favorite.title ?? "Untitled favorite";
}

function favoriteDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium"
  }).format(new Date(value));
}

function FavoriteCard({
  favorite,
  canRemove,
  pendingRemovalId,
  removingFavoriteId,
  onBeginRemoval,
  onCancelRemoval,
  onConfirmRemoval
}: Readonly<{
  favorite: Favorite;
  canRemove: boolean;
  pendingRemovalId: string | null;
  removingFavoriteId: string | null;
  onBeginRemoval: (favoriteId: string) => void;
  onCancelRemoval: () => void;
  onConfirmRemoval: (favoriteId: string) => Promise<void> | void;
}>): React.ReactElement {
  const title = favoriteTitle(favorite);
  const isPending = pendingRemovalId === favorite.favoriteId;
  const isRemoving = removingFavoriteId === favorite.favoriteId;

  return (
    <article className="favorite-card">
      <header className="favorite-card-header">
        <div>
          <p className="portal-page-eyebrow">{displayToken(favorite.mediaType)}</p>
          <h2 className="favorite-card-title">{title}</h2>
        </div>

        <span className="favorite-card-badge">{displayToken(favorite.provider)}</span>
      </header>

      <dl className="favorite-card-meta">
        <div>
          <dt>Added</dt>
          <dd>
            <time dateTime={favorite.createdAt}>{favoriteDate(favorite.createdAt)}</time>
          </dd>
        </div>
      </dl>

      {!canRemove ? (
        <p className="favorite-read-only">Read-only access</p>
      ) : isPending ? (
        <div
          aria-label={`Confirm removal of ${title}`}
          className="favorite-confirmation"
          role="group"
        >
          <p>Remove this item from your Favorites list?</p>

          <div className="favorite-card-actions">
            <button
              aria-label={`Confirm removal of ${title}`}
              className="favorite-remove-button"
              disabled={isRemoving}
              onClick={() => {
                void onConfirmRemoval(favorite.favoriteId);
              }}
              type="button"
            >
              {isRemoving ? "Removing…" : "Confirm removal"}
            </button>

            <button
              className="favorite-secondary-button"
              disabled={isRemoving}
              onClick={onCancelRemoval}
              type="button"
            >
              Keep favorite
            </button>
          </div>
        </div>
      ) : (
        <div className="favorite-card-actions">
          <button
            aria-label={`Remove ${title} from favorites`}
            className="favorite-remove-button"
            disabled={removingFavoriteId !== null}
            onClick={() => {
              onBeginRemoval(favorite.favoriteId);
            }}
            type="button"
          >
            Remove from favorites
          </button>
        </div>
      )}
    </article>
  );
}

export function FavoritesContent({
  state,
  canRemove,
  pendingRemovalId,
  removingFavoriteId,
  mutationError,
  onRetry,
  onBeginRemoval,
  onCancelRemoval,
  onConfirmRemoval
}: FavoritesContentProps): React.ReactElement {
  if (state.status === "loading") {
    return (
      <section aria-busy="true" aria-label="Loading favorites" className="favorites-grid">
        {Array.from({ length: 3 }, (_, index) => (
          <article className="favorite-card favorite-card-loading" key={index}>
            <span className="favorite-loading-line favorite-loading-line-short" />
            <span className="favorite-loading-line favorite-loading-line-title" />
            <span className="favorite-loading-line" />
          </article>
        ))}
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section
        aria-labelledby="favorites-error-title"
        className="favorites-message-panel"
        role="alert"
      >
        <p className="portal-page-eyebrow">Favorites unavailable</p>

        <h2 id="favorites-error-title">Atlas could not load your favorites</h2>

        <p>{state.error.message}</p>

        <button className="favorites-refresh-button" onClick={onRetry} type="button">
          Try again
        </button>
      </section>
    );
  }

  if (!state.data.length) {
    return (
      <section aria-labelledby="favorites-empty-title" className="favorites-message-panel">
        <p className="portal-page-eyebrow">No favorites yet</p>

        <h2 id="favorites-empty-title">Your Favorites list is empty</h2>

        <p>Media you mark as a favorite from supported Atlas experiences will appear here.</p>
      </section>
    );
  }

  return (
    <div className="favorites-view">
      {mutationError ? (
        <section
          aria-labelledby="favorites-mutation-error-title"
          className="favorites-mutation-error"
          role="alert"
        >
          <h2 id="favorites-mutation-error-title">Favorite could not be removed</h2>
          <p>{mutationError.message}</p>
        </section>
      ) : null}

      <section aria-label="Your favorites" className="favorites-grid">
        {state.data.map((favorite) => (
          <FavoriteCard
            canRemove={canRemove}
            favorite={favorite}
            key={favorite.favoriteId}
            onBeginRemoval={onBeginRemoval}
            onCancelRemoval={onCancelRemoval}
            onConfirmRemoval={onConfirmRemoval}
            pendingRemovalId={pendingRemovalId}
            removingFavoriteId={removingFavoriteId}
          />
        ))}
      </section>
    </div>
  );
}

export function FavoritesView({
  onRefreshStateChange
}: FavoritesViewProps = {}): React.ReactElement {
  const { can } = usePermission();
  const { state, refresh, removeFavorite, removingFavoriteId, mutationError } = useFavorites();

  const [pendingRemovalId, setPendingRemovalId] = useState<string | null>(null);

  const canRemove = can(ATLAS_PERMISSIONS.favoritesWrite);
  const isBusy = state.status === "loading" || removingFavoriteId !== null;

  useEffect(() => {
    onRefreshStateChange?.(refresh, isBusy);
  }, [isBusy, onRefreshStateChange, refresh]);

  const handleConfirmRemoval = useCallback(
    async (favoriteId: string): Promise<void> => {
      const removed = await removeFavorite(favoriteId);

      if (removed) {
        setPendingRemovalId(null);
      }
    },
    [removeFavorite]
  );

  return (
    <FavoritesContent
      canRemove={canRemove}
      mutationError={mutationError}
      onBeginRemoval={setPendingRemovalId}
      onCancelRemoval={() => {
        setPendingRemovalId(null);
      }}
      onConfirmRemoval={handleConfirmRemoval}
      onRetry={refresh}
      pendingRemovalId={pendingRemovalId}
      removingFavoriteId={removingFavoriteId}
      state={state}
    />
  );
}
