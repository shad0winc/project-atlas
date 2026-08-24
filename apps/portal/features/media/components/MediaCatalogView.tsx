"use client";

import { useCallback, useEffect, useState } from "react";

import { addFavorite } from "../../favorites";

import { ATLAS_PERMISSIONS } from "../../../lib/authorization/permissions";

import { usePermission } from "../../../lib/authorization/use-permission";

import { useAuth } from "../../../lib/auth/use-auth";

import { loadMediaCatalog } from "../api/catalog";

import type { MediaCatalogItem, MediaCatalogPage } from "../types/catalog";

type MediaCatalogContentProps = Readonly<{
  page: MediaCatalogPage | null;
  loading: boolean;
  error: string | null;
  canFavorite: boolean;
  favoritingItemId: string | null;
  favoritedItemIds: ReadonlySet<string>;
  onFavorite: (item: MediaCatalogItem) => void;
  onRetry: () => void;
}>;

function itemIdentity(item: MediaCatalogItem): string {
  return `${item.provider}\u0000${item.itemId}`;
}

export function MediaCatalogContent({
  page,
  loading,
  error,
  canFavorite,
  favoritingItemId,
  favoritedItemIds,
  onFavorite,
  onRetry
}: MediaCatalogContentProps): React.ReactElement {
  return (
    <section aria-label="Your Jellyfin library" className="media-discovery-view">
      <div className="media-discovery-results-header">
        <div>
          <p className="media-discovery-eyebrow">Jellyfin library</p>
          <h2>Available in your library</h2>
          <p className="media-discovery-overview">
            Save library media to your personal Favorites list.
          </p>
        </div>
      </div>

      {loading ? (
        <p aria-live="polite" className="media-discovery-message">
          Loading your Jellyfin library…
        </p>
      ) : null}

      {error !== null ? (
        <div className="media-discovery-message" role="alert">
          <p>{error}</p>
          <button className="media-discovery-secondary-button" onClick={onRetry} type="button">
            Retry library
          </button>
        </div>
      ) : null}

      {!loading && error === null && page !== null && page.items.length === 0 ? (
        <p className="media-discovery-message">
          Your Jellyfin library does not contain any catalog items yet.
        </p>
      ) : null}

      {!loading && error === null && page !== null && page.items.length > 0 ? (
        <div className="media-discovery-grid">
          {page.items.map((item) => {
            const identity = itemIdentity(item);
            const isFavoriting = favoritingItemId === identity;
            const isFavorited = favoritedItemIds.has(identity);

            return (
              <article className="media-discovery-card" key={identity}>
                <div className="media-discovery-card-header">
                  <div>
                    <p className="media-discovery-kind">{item.mediaType}</p>
                    <h3>{item.title}</h3>
                  </div>

                  {item.year !== undefined ? <span>{item.year}</span> : null}
                </div>

                {item.library !== undefined ? (
                  <p className="media-discovery-overview">Library: {item.library}</p>
                ) : null}

                <p className="media-discovery-status">Provider: {item.provider}</p>

                {canFavorite ? (
                  <button
                    aria-label={
                      isFavorited
                        ? `${item.title} added to favorites`
                        : `Add ${item.title} to favorites`
                    }
                    className="media-discovery-primary-button"
                    disabled={isFavoriting || isFavorited}
                    onClick={() => {
                      onFavorite(item);
                    }}
                    type="button"
                  >
                    {isFavorited
                      ? "Added to favorites"
                      : isFavoriting
                        ? "Adding…"
                        : "Add to favorites"}
                  </button>
                ) : (
                  <p className="media-discovery-read-only">
                    You can browse this library, but your account cannot modify Favorites.
                  </p>
                )}
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

export function MediaCatalogView(): React.ReactElement {
  const { user } = useAuth();
  const { can } = usePermission();

  const [page, setPage] = useState<MediaCatalogPage | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const [favoritingItemId, setFavoritingItemId] = useState<string | null>(null);

  const [favoritedItemIds, setFavoritedItemIds] = useState<ReadonlySet<string>>(() => new Set());

  const canFavorite = can(ATLAS_PERMISSIONS.favoritesWrite);

  const load = useCallback((): void => {
    setLoading(true);
    setError(null);

    void loadMediaCatalog({
      page: 1,
      pageSize: 24
    })
      .then((catalog) => {
        setPage(catalog);
      })
      .catch(() => {
        setError("Atlas could not load your Jellyfin library.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    let cancelled = false;

    void loadMediaCatalog({
      page: 1,
      pageSize: 24
    })
      .then((catalog) => {
        if (!cancelled) {
          setPage(catalog);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Atlas could not load your Jellyfin library.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleFavorite = useCallback(
    async (item: MediaCatalogItem): Promise<void> => {
      if (user === null) {
        setError("Your authenticated Atlas user is unavailable.");
        return;
      }

      const identity = itemIdentity(item);

      setFavoritingItemId(identity);
      setError(null);

      try {
        await addFavorite(
          {
            provider: item.provider,
            itemId: item.itemId
          },
          {
            expectedUserId: user.user_id
          }
        );

        setFavoritedItemIds((current) => {
          const next = new Set(current);
          next.add(identity);
          return next;
        });
      } catch {
        setError(`Atlas could not add ${item.title} to Favorites.`);
      } finally {
        setFavoritingItemId(null);
      }
    },
    [user]
  );

  return (
    <MediaCatalogContent
      canFavorite={canFavorite}
      error={error}
      favoritedItemIds={favoritedItemIds}
      favoritingItemId={favoritingItemId}
      loading={loading}
      onFavorite={(item) => {
        void handleFavorite(item);
      }}
      onRetry={load}
      page={page}
    />
  );
}
