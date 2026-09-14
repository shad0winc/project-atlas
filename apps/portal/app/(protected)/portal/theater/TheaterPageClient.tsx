"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { loadFavorites } from "../../../../features/favorites";
import { MediaCatalogView } from "../../../../features/media";
import { readMediaRetention } from "../../../../features/media/services/retention";
import { addFavoriteAndRefreshRetention } from "../../../../features/media/services/retention-mutations";
import { refreshMediaRetentionAfterMutation } from "../../../../features/media/services/retention-refresh";
import type { MediaRetention } from "../../../../features/media/types/retention";
import { loadPlaybackSession } from "../../../../features/playback/api/session";
import { AtlasTheaterPlayer } from "../../../../features/playback/components/AtlasTheaterPlayer";
import type { PlaybackSession } from "../../../../features/playback/types/session";
import { useAuth } from "../../../../lib/auth/use-auth";
import { ATLAS_PERMISSIONS } from "../../../../lib/authorization/permissions";
import { usePermission } from "../../../../lib/authorization/use-permission";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const theaterRoute = PORTAL_ROUTES.theater;

type TheaterState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "ready"; session: PlaybackSession }>
  | Readonly<{ status: "error"; message: string }>;

function AuthorizedTheaterPlayer({
  session
}: Readonly<{
  session: PlaybackSession;
}>): React.ReactElement {
  const { user } = useAuth();
  const { can } = usePermission();

  const [retention, setRetention] =
    useState<MediaRetention | null>(null);

  const [favoriteState, setFavoriteState] =
    useState<
      "loading" |
      "idle" |
      "submitting" |
      "complete" |
      "unavailable"
    >("loading");

  const canReadFavorites =
    user !== null &&
    can(ATLAS_PERMISSIONS.favoritesRead);

  const canFavorite =
    user !== null &&
    can(ATLAS_PERMISSIONS.favoritesWrite);

  const canDislike =
    user !== null &&
    can(ATLAS_PERMISSIONS.dislikesWrite);

  useEffect(() => {
    const controller = new AbortController();

    setRetention(null);
    setFavoriteState("loading");

    void readMediaRetention(
      session.provider,
      session.playableTargetId,
      controller.signal
    )
      .then((nextRetention) => {
        if (!controller.signal.aborted) {
          setRetention(nextRetention);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setRetention(null);
        }
      });

    if (
      user === null ||
      !canReadFavorites
    ) {
      setFavoriteState("unavailable");
    } else {
      void loadFavorites({
        expectedUserId: user.user_id
      })
        .then((favorites) => {
          if (controller.signal.aborted) {
            return;
          }

          const isFavorited = favorites.some(
            (favorite) =>
              favorite.provider === session.provider &&
              favorite.itemId === session.playableTargetId
          );

          setFavoriteState(
            isFavorited ? "complete" : "idle"
          );
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setFavoriteState("unavailable");
          }
        });
    }

    return () => {
      controller.abort();
    };
  }, [
    canReadFavorites,
    session.playableTargetId,
    session.provider,
    user
  ]);

  const handleFavorite = useCallback(
    async (): Promise<void> => {
      if (user === null || !canFavorite) {
        return;
      }

      setFavoriteState("submitting");

      try {
        const result =
          await addFavoriteAndRefreshRetention(
            {
              provider: session.provider,
              itemId: session.playableTargetId
            },
            {
              expectedUserId: user.user_id
            }
          );

        setRetention(
          result.status === "available"
            ? result.retention
            : null
        );

        setFavoriteState("complete");
      } catch {
        setFavoriteState("idle");
      }
    },
    [
      canFavorite,
      session.playableTargetId,
      session.provider,
      user
    ]
  );

  const handleDisliked = useCallback(
    async (): Promise<void> => {
      const result =
        await refreshMediaRetentionAfterMutation(
          session.provider,
          session.playableTargetId
        );

      setRetention(
        result.status === "available"
          ? result.retention
          : null
      );
    },
    [
      session.playableTargetId,
      session.provider
    ]
  );

  return (
    <AtlasTheaterPlayer
      canDislike={canDislike}
      canFavorite={canFavorite}
      dislikeExpectedUserId={
        canDislike && user !== null
          ? user.user_id
          : undefined
      }
      favoriteState={favoriteState}
      onDisliked={handleDisliked}
      onFavorite={handleFavorite}
      retention={retention}
      session={session}
    />
  );
}

export function TheaterPageClient(): React.ReactElement {
  const searchParams = useSearchParams();
  const provider = searchParams.get("provider")?.trim() ?? "";
  const itemId = searchParams.get("item")?.trim() ?? "";

  const [state, setState] = useState<TheaterState>({
    status: "loading"
  });

  const hasValidTarget = Boolean(provider && itemId);

  useEffect(() => {
    if (!hasValidTarget) {
      return;
    }

    const controller = new AbortController();

    void loadPlaybackSession(provider, itemId, controller.signal)
      .then((session) => {
        if (!session.available) {
          throw new Error("Playback is not currently available.");
        }
        setState({ status: "ready", session });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        setState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "Atlas could not prepare playback."
        });
      });

    return () => {
      controller.abort();
    };
  }, [hasValidTarget, itemId, provider]);

  if (!hasValidTarget) {
    return (
      <PortalPage
        accessDeniedDescription="Your Atlas account does not have permission to use Theater."
        description={
          theaterRoute.pageDescription ??
          "Open your Atlas playback hub or continue to an exact playable item."
        }
        eyebrow={theaterRoute.label}
        permission={theaterRoute.permission}
        title="Theater"
      >
        <section aria-labelledby="theater-library-title" className="media-discovery-view">
          <div className="media-discovery-results-header">
            <div>
              <p className="media-discovery-eyebrow">Playback hub</p>
              <h2 id="theater-library-title">Available to watch</h2>
              <p className="media-discovery-overview">
                Choose an available item and Atlas will hand playback to Jellyfin.
              </p>
            </div>
          </div>
          <MediaCatalogView />
        </section>
      </PortalPage>
    );
  }

  if (state.status === "error") {
    return (
      <section aria-labelledby="theater-error-title">
        <p className="portal-page-eyebrow">Theater</p>
        <h1 id="theater-error-title">Playback unavailable</h1>
        <p>{state.message}</p>
        <Link href="/portal/media">Return to Media</Link>
      </section>
    );
  }

  if (state.status === "ready") {
    return (
      <PortalPage
        accessDeniedDescription="Your Atlas account does not have permission to use Theater."
        description="Secure Atlas playback powered by Jellyfin."
        eyebrow={theaterRoute.label}
        permission={theaterRoute.permission}
        title={state.session.title}
      >
        <section aria-labelledby="atlas-player-title" className="media-discovery-view">
          <div className="media-discovery-results-header">
            <div>
              <p className="media-discovery-eyebrow">Atlas Theater</p>
              <h2 id="atlas-player-title">{state.session.title}</h2>
              <p className="media-discovery-overview">
                Atlas is the playback interface. Jellyfin selects and delivers the compatible media stream.
              </p>
            </div>
          </div>
          <AuthorizedTheaterPlayer
            key={[
              state.session.provider,
              state.session.requestedTargetId,
              state.session.playableTargetId
            ].join(":")}
            session={state.session}
          />
        </section>
      </PortalPage>
    );
  }

  return (
    <section aria-busy="true" aria-labelledby="theater-loading-title">
      <p className="portal-page-eyebrow">Theater</p>
      <h1 id="theater-loading-title">Preparing playback</h1>
      <p>Atlas is preparing the exact playable item.</p>
    </section>
  );
}
