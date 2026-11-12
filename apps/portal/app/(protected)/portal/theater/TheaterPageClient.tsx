"use client";

import Link from "next/link";
import { Fragment } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { loadFavorites } from "../../../../features/favorites";
import { readMediaRetention } from "../../../../features/media/services/retention";
import { addFavoriteAndRefreshRetention } from "../../../../features/media/services/retention-mutations";
import { refreshMediaRetentionAfterMutation } from "../../../../features/media/services/retention-refresh";
import { sourceQuality } from "../../../../features/media/types/quality";
import type { MediaRetention } from "../../../../features/media/types/retention";
import { loadPlaybackSession } from "../../../../features/playback/api/session";
import { SeriesAiringNotice } from "../../../../features/media/components/SeriesAiringNotice";
import { readMediaSeriesDetail } from "../../../../features/media/services/series";
import type { MediaSeriesDetail } from "../../../../features/media/types/series";
import { SeriesEpisodeNavigation } from "../../../../features/media/components/SeriesEpisodeNavigation";
import { episodeHref } from "../../../../features/playback/services/episode-navigation";
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

function TheaterSeriesAiringNotice({ providerMediaId }: { providerMediaId: string }) {
  const { can } = usePermission();
  const canReadMedia = can(ATLAS_PERMISSIONS.mediaRead);
  const [detail, setDetail] = useState<MediaSeriesDetail | null>(null);

  useEffect(() => {
    if (!canReadMedia) return;

    const controller = new AbortController();
    void readMediaSeriesDetail({ providerMediaId, signal: controller.signal })
      .then(result => {
        if (!controller.signal.aborted) setDetail(result);
      })
      .catch(() => {
        // Discovery is optional while a title is playing.
      });
    return () => controller.abort();
  }, [canReadMedia, providerMediaId]);

  return canReadMedia && detail ? <SeriesAiringNotice detail={detail} /> : null;
}

function AuthorizedTheaterPlayer({
  session
}: Readonly<{
  session: PlaybackSession;
}>): React.ReactElement {
  const { user } = useAuth();
  const router = useRouter();
  const [autoAdvance, setAutoAdvance] = useState(true);
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

  const [
    favoriteStateIdentity,
    setFavoriteStateIdentity
  ] = useState<string | null>(null);

  const canReadFavorites =
    user !== null &&
    can(ATLAS_PERMISSIONS.favoritesRead);

  const canFavorite =
    user !== null &&
    can(ATLAS_PERMISSIONS.favoritesWrite);

  const canDislike =
    user !== null &&
    can(ATLAS_PERMISSIONS.dislikesWrite);

  const currentFavoriteIdentity =
    user === null
      ? null
      : [
          user.user_id,
          session.provider,
          session.playableTargetId
        ].join("\u0000");

  const effectiveFavoriteState =
    user === null ||
    !canReadFavorites
      ? "unavailable"
      : favoriteStateIdentity === currentFavoriteIdentity
        ? favoriteState
        : "loading";

  useEffect(() => {
    const controller = new AbortController();

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
      user !== null &&
      canReadFavorites
    ) {
      const expectedFavoriteIdentity = [
        user.user_id,
        session.provider,
        session.playableTargetId
      ].join("\u0000");

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

          setFavoriteStateIdentity(
            expectedFavoriteIdentity
          );

          setFavoriteState(
            isFavorited ? "complete" : "idle"
          );
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setFavoriteStateIdentity(
              expectedFavoriteIdentity
            );
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

      const expectedFavoriteIdentity = [
        user.user_id,
        session.provider,
        session.playableTargetId
      ].join("\u0000");

      setFavoriteStateIdentity(
        expectedFavoriteIdentity
      );
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
    <>
    <AtlasTheaterPlayer
      autoAdvance={autoAdvance}
      onNextEpisode={(nextId) => router.push(episodeHref(session.provider, nextId))}
      canDislike={canDislike}
      canFavorite={canFavorite}
      dislikeExpectedUserId={
        canDislike && user !== null
          ? user.user_id
          : undefined
      }
      favoriteState={effectiveFavoriteState}
      onDisliked={handleDisliked}
      onFavorite={handleFavorite}
      retention={retention}
      session={session}
      viewerId={user?.user_id}
      key={JSON.stringify([user?.user_id, session.provider, session.playableTargetId])}
    />
    {session.seriesId && session.sourceType === "library" ? (
      <section aria-label="Episode controls" className="atlas-theater-player-meta">
        {session.previousTargetId ? <Link href={episodeHref(session.provider, session.previousTargetId)}>Previous episode</Link> : null}
        {session.nextTargetId ? <Link href={episodeHref(session.provider, session.nextTargetId)}>Next episode</Link> : <span>Last available episode</span>}
        <label><input type="checkbox" checked={autoAdvance} onChange={(event) => setAutoAdvance(event.target.checked)} /> Play next episode automatically</label>
        <SeriesEpisodeNavigation key={session.seriesId} provider={session.provider} seriesId={session.seriesId} currentEpisodeId={session.playableTargetId} title="This series" />
      </section>
    ) : null}
    </>
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
        <Link href={`${PORTAL_ROUTES.media.path}?view=library`}>Choose a title in Library</Link>
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
    const { session } = state;
    const credits = [
      ["Cast", session.cast],
      ["Directors", session.directors],
      ["Producers", session.producers],
      ["Production origin", session.productionLocations],
    ] as const;
    return (
      <PortalPage
        accessDeniedDescription="Your Atlas account does not have permission to use Theater."
        description="Secure Atlas playback powered by Jellyfin."
        eyebrow={theaterRoute.label}
        permission={theaterRoute.permission}
        title={state.session.title}
      >
        <div className="theater-layout">
          <section aria-label="Theater player">
            <AuthorizedTheaterPlayer
              key={JSON.stringify([state.session.provider, state.session.requestedTargetId, state.session.playableTargetId])}
              session={state.session}
            />
          </section>
          <section className="portal-home-card" aria-labelledby="theater-details-title">
            <h3 id="theater-details-title">About this title</h3>
            <p>{state.session.overview ?? "A summary is unavailable for this title."}</p>
            {session.seriesTmdbId && (
              <TheaterSeriesAiringNotice key={session.seriesTmdbId} providerMediaId={session.seriesTmdbId} />
            )}
            <dl>
              <dt>Source</dt>
              <dd>{state.session.provider === "jellyfin" ? "Jellyfin" : state.session.provider}</dd>
              {session.sourceType === "library" && (
                <>
                  <dt>Source quality</dt>
                  <dd>{sourceQuality(session.videoWidth, session.videoHeight)}</dd>
                </>
              )}
              {credits.map(([label, names]) => names?.length ? (
                <Fragment key={label}>
                  <dt>{label}</dt>
                  <dd>{names.join(", ")}</dd>
                </Fragment>
              ) : null)}
              {state.session.durationTicks && state.session.durationTicks > 0 ? (
                <>
                  <dt>Runtime</dt>
                  <dd>{Math.ceil(state.session.durationTicks / 600_000_000)} min</dd>
                </>
              ) : null}
            </dl>
            <Link href={`${PORTAL_ROUTES.media.path}?view=library`}>Back to Library</Link>
          </section>
        </div>
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
