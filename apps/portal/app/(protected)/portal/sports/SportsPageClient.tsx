"use client";

import { useCallback, useEffect, useState } from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";
import {
  SportsRequestView,
  followSports,
  loadSportsEvents,
  loadSportsFollows,
  requestSportsEvent,
  searchSports,
  unfollowSports,
  updateSportsRecordingIntent,
  type SportsEvent,
  type SportsFollow,
  type SportsRequestInput,
  type SportsSearchResult,
  type SportsSubscription
} from "../../../../features/sports";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const sportsRoute = PORTAL_ROUTES.sports;

export function SportsPageClient(): React.ReactElement {
  const [events, setEvents] = useState<readonly SportsEvent[]>([]);
  const [follows, setFollows] = useState<readonly SportsFollow[]>([]);
  const [searchResults, setSearchResults] = useState<readonly SportsSearchResult[]>([]);
  const [searchType, setSearchType] = useState<"team" | "league">("team");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      const [loadedEvents, loadedFollows] = await Promise.all([
        loadSportsEvents(),
        loadSportsFollows()
      ]);

      setEvents(loadedEvents);
      setFollows(loadedFollows);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Atlas could not load Sports."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    void Promise.all([
      loadSportsEvents({ signal: controller.signal }),
      loadSportsFollows({ signal: controller.signal })
    ])
      .then(([loadedEvents, loadedFollows]) => {
        if (!controller.signal.aborted) {
          setEvents(loadedEvents);
          setFollows(loadedFollows);
        }
      })
      .catch((loadError) => {
        if (!controller.signal.aborted) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Atlas could not load Sports."
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, []);

  async function handleSearch(
    type: "team" | "league",
    query: string
  ): Promise<void> {
    setSearchType(type);
    setSearchResults(await searchSports(type, query));
  }

  async function handleFollow(
    type: "team" | "league",
    providerId: string
  ): Promise<void> {
    const follow = await followSports(type, providerId);

    setFollows((current) =>
      current.some((item) => item.subscriptionId === follow.subscriptionId)
        ? current
        : [...current, follow]
    );
  }

  async function handleUnfollow(
    subscriptionId: string
  ): Promise<void> {
    await unfollowSports(subscriptionId);

    setFollows((current) =>
      current.filter((item) => item.subscriptionId !== subscriptionId)
    );
  }

  async function handleBrowse(
    type: "team" | "league",
    providerId: string
  ): Promise<void> {
    setEvents(
      await loadSportsEvents(
        {},
        type === "team"
          ? { teamIds: [providerId] }
          : { leagueIds: [providerId] }
      )
    );
  }

  async function handleRequestEvent(
    input: SportsRequestInput
  ): Promise<SportsSubscription> {
    const subscription = await requestSportsEvent(input);

    setEvents((current) =>
      current.map((event) =>
        event.provider === subscription.provider &&
        event.providerEventId === subscription.providerEventId
          ? { ...event, requested: true }
          : event
      )
    );

    return subscription;
  }

  async function handleSetRecording(
    event: SportsEvent,
    record: boolean
  ): Promise<void> {
    let eventFollow = follows.find(
      (follow) =>
        follow.type === "event" &&
        follow.provider === event.provider &&
        follow.providerId === event.providerEventId
    );

    if (!eventFollow) {
      const created = await followSports("event", event.providerEventId);
      eventFollow = created;
      setFollows((current) =>
        current.some((item) => item.subscriptionId === created.subscriptionId)
          ? current
          : [...current, created]
      );
      setEvents((current) =>
        current.map((item) =>
          item.provider === event.provider &&
          item.providerEventId === event.providerEventId
            ? { ...item, requested: true }
            : item
        )
      );
    }

    const updated = await updateSportsRecordingIntent(
      eventFollow.subscriptionId,
      record
    );
    setFollows((current) =>
      current.some((item) => item.subscriptionId === updated.subscriptionId)
        ? current.map((item) =>
            item.subscriptionId === updated.subscriptionId ? updated : item
          )
        : [...current, updated]
    );
  }

  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to browse Sports events."
      description={
        sportsRoute.pageDescription ??
        "Discover teams and leagues, follow your favorites, and browse upcoming sporting events."
      }
      eyebrow={sportsRoute.label}
      permission={sportsRoute.permission}
      title="Sports"
    >
      {loading ? (
        <section
          aria-busy="true"
          aria-label="Loading Sports"
          className="requests-grid"
        >
          <p>Loading Sports...</p>
        </section>
      ) : error ? (
        <section
          aria-labelledby="sports-load-error-title"
          className="requests-message-panel"
        >
          <p className="portal-page-eyebrow">Sports unavailable</p>
          <h2 id="sports-load-error-title">Atlas could not load Sports</h2>
          <p>{error}</p>
          <button
            className="requests-refresh-button"
            onClick={() => { void load(); }}
            type="button"
          >
            Retry
          </button>
        </section>
      ) : (
        <SportsRequestView
          events={events}
          follows={follows}
          onBrowse={handleBrowse}
          onFollow={handleFollow}
          onRequestEvent={handleRequestEvent}
          onSetRecording={handleSetRecording}
          onSearch={handleSearch}
          onUnfollow={handleUnfollow}
          searchResults={searchResults}
          searchType={searchType}
        />
      )}
    </PortalPage>
  );
}
