"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { MediaCatalogView } from "../../../../features/media";
import { loadPlaybackSession } from "../../../../features/playback/api/session";
import { AtlasTheaterPlayer } from "../../../../features/playback/components/AtlasTheaterPlayer";
import type { PlaybackSession } from "../../../../features/playback/types/session";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const theaterRoute = PORTAL_ROUTES.theater;

type TheaterState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "ready"; session: PlaybackSession }>
  | Readonly<{ status: "error"; message: string }>;

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
          <AtlasTheaterPlayer session={state.session} />
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
