"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState
} from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";
import { AtlasTheaterPlayer } from "../../../../features/playback/components/AtlasTheaterPlayer";
import type { SubtitleSelection } from "../../../../features/playback/services/session";
import type { PlaybackSession } from "../../../../features/playback/types/session";
import {
  SportsRequestView,
  createSportsLiveSession,
  followSports,
  heartbeatSportsLiveSession,
  loadSportsEvents,
  loadSportsFollows,
  loadSportsLiveAvailability,
  releaseSportsLiveSession,
  requestSportsEvent,
  searchSports,
  unfollowSports,
  updateSportsRecordingIntent,
  type SportsEvent,
  type SportsFollow,
  type SportsLiveAvailability,
  type SportsLiveSessionResult,
  type SportsRequestInput,
  type SportsSearchResult,
  type SportsSearchType,
  type SportsSubscription
} from "../../../../features/sports";
import { reconcileFollowedEventMetadata } from "../../../../features/sports/services/followedEventMetadata";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const sportsRoute = PORTAL_ROUTES.sports;

export function SportsPageClient(): React.ReactElement {
  const [events, setEvents] = useState<readonly SportsEvent[]>([]);
  const [followedEvents, setFollowedEvents] =
    useState<readonly SportsEvent[]>([]);
  const [follows, setFollows] = useState<readonly SportsFollow[]>([]);
  const [
    liveAvailabilityByEvent,
    setLiveAvailabilityByEvent
  ] = useState<Readonly<Record<string, SportsLiveAvailability>>>({});
  const [searchResults, setSearchResults] = useState<readonly SportsSearchResult[]>([]);
  const [searchType, setSearchType] = useState<SportsSearchType>("team");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [
    activeLiveSession,
    setActiveLiveSession
  ] = useState<SportsLiveSessionResult | null>(null);

  const [
    livePlaybackError,
    setLivePlaybackError
  ] = useState<string | null>(null);

  const activeLiveSessionRef =
    useRef<SportsLiveSessionResult | null>(null);

  const liveHeartbeatTimeoutRef =
    useRef<ReturnType<typeof setTimeout> | null>(null);

  const liveRequestVersionRef = useRef(0);

  function clearLiveHeartbeat(): void {
    if (liveHeartbeatTimeoutRef.current !== null) {
      clearTimeout(liveHeartbeatTimeoutRef.current);
      liveHeartbeatTimeoutRef.current = null;
    }
  }

  async function releaseLiveSessionBestEffort(
    liveSessionId: string
  ): Promise<void> {
    try {
      await releaseSportsLiveSession(liveSessionId);
    } catch {
      // Server TTL remains the final fail-safe if explicit release fails.
    }
  }

  function scheduleLiveHeartbeat(
    liveSession: SportsLiveSessionResult
  ): void {
    clearLiveHeartbeat();

    const { liveSessionId, ttlSeconds } = liveSession;

    const delayMs = Math.max(
      1_000,
      Math.floor((ttlSeconds * 1000) / 2)
    );

    liveHeartbeatTimeoutRef.current = setTimeout(() => {
      void heartbeatSportsLiveSession(liveSessionId)
        .then((heartbeat) => {
          const current = activeLiveSessionRef.current;

          if (
            current === null ||
            current.liveSessionId !== liveSessionId
          ) {
            return;
          }

          const refreshed: SportsLiveSessionResult =
            Object.freeze({
              ...current,
              ttlSeconds: heartbeat.ttlSeconds
            });

          activeLiveSessionRef.current = refreshed;
          scheduleLiveHeartbeat(refreshed);
        })
        .catch(() => {
          const current = activeLiveSessionRef.current;

          if (
            current === null ||
            current.liveSessionId !== liveSessionId
          ) {
            return;
          }

          clearLiveHeartbeat();
          activeLiveSessionRef.current = null;
          setActiveLiveSession(null);
          setLivePlaybackError(
            "Atlas lost the authenticated live playback lease."
          );

          void releaseLiveSessionBestEffort(
            liveSessionId
          );
        });
    }, delayMs);
  }

  async function handleWatchLive(
    atlasChannelId: string
  ): Promise<void> {
    const requestVersion =
      liveRequestVersionRef.current + 1;

    liveRequestVersionRef.current = requestVersion;
    setLivePlaybackError(null);

    let nextLiveSession: SportsLiveSessionResult;

    try {
      nextLiveSession = await createSportsLiveSession(
        atlasChannelId
      );
    } catch (watchError) {
      if (
        liveRequestVersionRef.current === requestVersion
      ) {
        setLivePlaybackError(
          watchError instanceof Error
            ? watchError.message
            : "Atlas could not start live playback."
        );
      }

      return;
    }

    if (
      liveRequestVersionRef.current !== requestVersion
    ) {
      void releaseLiveSessionBestEffort(
        nextLiveSession.liveSessionId
      );
      return;
    }

    const previous =
      activeLiveSessionRef.current;

    activeLiveSessionRef.current = nextLiveSession;
    setActiveLiveSession(nextLiveSession);
    scheduleLiveHeartbeat(nextLiveSession);

    if (
      previous !== null &&
      previous.liveSessionId !==
        nextLiveSession.liveSessionId
    ) {
      void releaseLiveSessionBestEffort(
        previous.liveSessionId
      );
    }
  }

  async function resolveSportsLiveSession(
    provider: string,
    itemId: string,
    signal?: AbortSignal,
    subtitle: SubtitleSelection = "auto"
  ): Promise<PlaybackSession> {
    const current = activeLiveSessionRef.current;

    if (current === null) {
      throw new Error(
        "Sports live playback is no longer active."
      );
    }

    if (
      provider !== current.session.provider ||
      itemId !== current.session.playableTargetId
    ) {
      throw new Error(
        "Sports live playback identity changed unexpectedly."
      );
    }

    const requestVersion =
      liveRequestVersionRef.current + 1;

    liveRequestVersionRef.current = requestVersion;

    const replacement =
      await createSportsLiveSession(
        current.atlasChannelId,
        { signal },
        subtitle
      );

    if (
      liveRequestVersionRef.current !== requestVersion ||
      activeLiveSessionRef.current?.liveSessionId !==
        current.liveSessionId
    ) {
      void releaseLiveSessionBestEffort(
        replacement.liveSessionId
      );

      throw new Error(
        "Sports live playback changed while updating captions."
      );
    }

    activeLiveSessionRef.current = replacement;
    scheduleLiveHeartbeat(replacement);

    void releaseLiveSessionBestEffort(
      current.liveSessionId
    );

    return replacement.session;
  }

  function closeLivePlayback(): void {
    liveRequestVersionRef.current += 1;
    clearLiveHeartbeat();

    const current = activeLiveSessionRef.current;

    activeLiveSessionRef.current = null;
    setActiveLiveSession(null);
    setLivePlaybackError(null);

    if (current !== null) {
      void releaseLiveSessionBestEffort(
        current.liveSessionId
      );
    }
  }

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
    return () => {
      liveRequestVersionRef.current += 1;
      clearLiveHeartbeat();

      const current =
        activeLiveSessionRef.current;

      activeLiveSessionRef.current = null;

      if (current !== null) {
        void releaseLiveSessionBestEffort(
          current.liveSessionId
        );
      }
    };
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

  useEffect(() => {
    const controller = new AbortController();
    const eventIdsByProvider = new Map<string, Set<string>>();

    for (const follow of follows) {
      if (follow.type !== "event" || !follow.enabled) {
        continue;
      }

      const eventIds =
        eventIdsByProvider.get(follow.provider) ?? new Set<string>();

      eventIds.add(follow.providerId);
      eventIdsByProvider.set(follow.provider, eventIds);
    }

    const providers = Array.from(eventIdsByProvider.keys());

    const requests = providers.map((provider) =>
      loadSportsEvents(
        { signal: controller.signal },
        {
          provider,
          eventIds: Array.from(
            eventIdsByProvider.get(provider) ?? []
          )
        }
      )
    );

    void Promise.allSettled(requests).then((results) => {
      if (controller.signal.aborted) {
        return;
      }

      setFollowedEvents((current) =>
        reconcileFollowedEventMetadata(
          current,
          follows,
          providers,
          results
        )
      );
    });

    return () => {
      controller.abort();
    };
  }, [follows]);

  useEffect(() => {
    const controller = new AbortController();

    const eventFollows = follows.filter(
      (follow) => follow.type === "event"
    );

    void Promise.all(
      eventFollows.map(async (follow) => {
        const identity =
          `${follow.provider}:${follow.providerId}`;

        try {
          const availability =
            await loadSportsLiveAvailability(
              follow.provider,
              follow.providerId,
              { signal: controller.signal }
            );

          return [identity, availability] as const;
        } catch {
          return null;
        }
      })
    ).then((resolved) => {
      if (controller.signal.aborted) {
        return;
      }

      const nextAvailability: Record<
        string,
        SportsLiveAvailability
      > = {};

      for (const entry of resolved) {
        if (entry !== null) {
          nextAvailability[entry[0]] = entry[1];
        }
      }

      setLiveAvailabilityByEvent(nextAvailability);
    });

    return () => {
      controller.abort();
    };
  }, [follows]);

  async function handleSearch(
    type: SportsSearchType,
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

    setSearchResults((current) =>
      current.filter((item) => item.id !== providerId)
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
    const loadedEvents = await loadSportsEvents(
      {},
      type === "team"
        ? { teamIds: [providerId] }
        : { leagueIds: [providerId] }
    );

    setEvents(loadedEvents);

    window.requestAnimationFrame(() => {
      document
        .getElementById("sports-upcoming-events")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
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
    setSearchResults((current) =>
      current.map((result) =>
        result.kind === "event" &&
        result.provider === subscription.provider &&
        result.id === subscription.providerEventId
          ? { ...result, requested: true }
          : result
      )
    );
    setFollows((current) => {
      const follow = {
        subscriptionId: subscription.subscriptionId,
        type: "event" as const,
        provider: subscription.provider,
        providerId: subscription.providerEventId,
        name: subscription.name,
        userId: subscription.userId,
        enabled: subscription.enabled,
        record: false,
        createdAt: subscription.createdAt
      };

      return current.some(
        (item) => item.subscriptionId === follow.subscriptionId
      )
        ? current
        : [...current, follow];
    });

    return subscription;
  }

  async function handleSetRecording(
    event: Pick<SportsEvent, "provider" | "providerEventId">,
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
      {livePlaybackError !== null ? (
        <section
          aria-label="Sports live playback error"
          className="requests-message-panel"
        >
          <p role="alert">{livePlaybackError}</p>
        </section>
      ) : null}

      {activeLiveSession !== null ? (
        <section
          aria-label="Sports live playback"
          className="requests-message-panel"
        >
          <div className="requests-toolbar">
            <button
              aria-label="Close live playback"
              className="requests-refresh-button"
              onClick={closeLivePlayback}
              type="button"
            >
              Close live playback
            </button>
          </div>

          <AtlasTheaterPlayer
            key={activeLiveSession.atlasChannelId}
            session={activeLiveSession.session}
            sessionResolver={resolveSportsLiveSession}
          />
        </section>
      ) : null}

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
          followedEvents={followedEvents}
          follows={follows}
          liveAvailabilityByEvent={liveAvailabilityByEvent}
          onBrowse={handleBrowse}
          onWatchLive={handleWatchLive}
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
