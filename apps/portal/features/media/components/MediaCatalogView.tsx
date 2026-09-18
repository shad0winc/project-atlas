"use client";

import { useCallback, useEffect, useState } from "react";

import { DislikeAction } from "../../dislikes";
import { loadFavorites } from "../../favorites";
import { WatchAction } from "../../playback/components/WatchAction";
import { MediaRetentionStatus } from "./MediaRetentionStatus";
import { SeriesEpisodeNavigation } from "./SeriesEpisodeNavigation";

import { ATLAS_PERMISSIONS } from "../../../lib/authorization/permissions";

import { usePermission } from "../../../lib/authorization/use-permission";

import { useAuth } from "../../../lib/auth/use-auth";

import { loadMediaCatalog } from "../api/catalog";

import { applyMediaRetentionRefreshResult } from "../services/retention-integration";
import { addFavoriteAndRefreshRetention } from "../services/retention-mutations";
import { refreshMediaRetentionAfterMutation } from "../services/retention-refresh";

import type { MediaCatalogItem, MediaCatalogPage } from "../types/catalog";
import type { MediaRetention } from "../types/retention";

type MediaCatalogContentProps = Readonly<{
  page: MediaCatalogPage | null;
  retentionByItemId?: ReadonlyMap<string, MediaRetention>;
  loading: boolean;
  error: string | null;
  canFavorite: boolean;
  canDislike?: boolean;
  dislikeExpectedUserId?: string;
  onDisliked?: (item: MediaCatalogItem) => void | Promise<void>;
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
  retentionByItemId,
  loading,
  error,
  canFavorite,
  canDislike = false,
  dislikeExpectedUserId,
  onDisliked,
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
            const retention = retentionByItemId?.get(identity);

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

                {retention !== undefined ? (
                  <MediaRetentionStatus retention={retention} />
                ) : null}


                {item.mediaType === "tv" ||
                item.mediaType === "anime_tv" ? (
                  <SeriesEpisodeNavigation
                    provider={item.provider}
                    seriesId={item.itemId}
                    title={item.title}
                  />
                ) : (
                  <WatchAction
                    provider={item.provider}
                    itemId={item.itemId}
                  />
                )}
                {canDislike && dislikeExpectedUserId ? (
                  <DislikeAction
                    expectedUserId={dislikeExpectedUserId}
                    itemId={item.itemId}
                    onDisliked={
                      onDisliked === undefined
                        ? undefined
                        : () => onDisliked(item)
                    }
                    provider={item.provider}
                    title={item.title}
                  />
                ) : null}

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

  const [favoritedItemIds, setFavoritedItemIds] =
    useState<ReadonlySet<string>>(() => new Set());

  const [
    favoritesLoadedForUserId,
    setFavoritesLoadedForUserId
  ] = useState<string | null>(null);

  const [retentionByItemId, setRetentionByItemId] =
    useState<ReadonlyMap<string, MediaRetention>>(
      () => new Map()
    );

  const canReadFavorites =
    can(ATLAS_PERMISSIONS.favoritesRead);

  const canFavorite =
    can(ATLAS_PERMISSIONS.favoritesWrite);

  const canDislike =
    can(ATLAS_PERMISSIONS.dislikesWrite);

  const favoritesReady =
    user !== null &&
    canReadFavorites &&
    favoritesLoadedForUserId === user.user_id;

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

    if (
      user === null ||
      !canReadFavorites
    ) {
      return () => {
        cancelled = true;
      };
    }

    const expectedUserId = user.user_id;

    void loadFavorites({
      expectedUserId
    })
      .then((favorites) => {
        if (cancelled) {
          return;
        }

        setFavoritedItemIds(
          new Set(
            favorites.map(
              (favorite) =>
                `${favorite.provider}\u0000${favorite.itemId}`
            )
          )
        );

        setFavoritesLoadedForUserId(
          expectedUserId
        );
      })
      .catch(() => {
        if (!cancelled) {
          setFavoritedItemIds(new Set());
          setFavoritesLoadedForUserId(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    canReadFavorites,
    user
  ]);

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
          setError(
            "Atlas could not load your Jellyfin library."
          );
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
        const retentionResult =
          await addFavoriteAndRefreshRetention(
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

        setRetentionByItemId((current) =>
          applyMediaRetentionRefreshResult(
            current,
            item.provider,
            item.itemId,
            retentionResult
          )
        );
      } catch {
        setError(`Atlas could not add ${item.title} to Favorites.`);
      } finally {
        setFavoritingItemId(null);
      }
    },
    [user]
  );

  const handleDisliked = useCallback(
    async (item: MediaCatalogItem): Promise<void> => {
      const retentionResult =
        await refreshMediaRetentionAfterMutation(
          item.provider,
          item.itemId
        );

      setRetentionByItemId((current) =>
        applyMediaRetentionRefreshResult(
          current,
          item.provider,
          item.itemId,
          retentionResult
        )
      );
    },
    []
  );

  return (
    <MediaCatalogContent
      canFavorite={
        canFavorite &&
        favoritesReady
      }
      canDislike={canDislike}
      dislikeExpectedUserId={
        canDislike && user !== null
          ? user.user_id
          : undefined
      }
      error={error}
      favoritedItemIds={favoritedItemIds}
      favoritingItemId={favoritingItemId}
      loading={loading}
      onDisliked={handleDisliked}
      onFavorite={(item) => {
        void handleFavorite(item);
      }}
      onRetry={load}
      page={page}
      retentionByItemId={retentionByItemId}
    />
  );
}
