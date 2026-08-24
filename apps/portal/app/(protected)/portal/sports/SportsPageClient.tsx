"use client";

import { useCallback, useEffect, useState } from "react";

import { PortalPage } from "../../../../components/portal/PortalPage";
import {
  SportsRequestView,
  loadSportsEvents,
  requestSportsEvent,
  type SportsEvent,
  type SportsRequestInput,
  type SportsSubscription
} from "../../../../features/sports";
import { PORTAL_ROUTES } from "../../../../lib/navigation/portal";

const sportsRoute = PORTAL_ROUTES.sports;

export function SportsPageClient(): React.ReactElement {
  const [events, setEvents] = useState<readonly SportsEvent[]>([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      setEvents(await loadSportsEvents());
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : "Atlas could not load Sports events."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    void loadSportsEvents({
      signal: controller.signal
    })
      .then((loadedEvents) => {
        if (!controller.signal.aborted) {
          setEvents(loadedEvents);
        }
      })
      .catch((loadError) => {
        if (!controller.signal.aborted) {
          setError(
            loadError instanceof Error ? loadError.message : "Atlas could not load Sports events."
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

  async function handleRequestEvent(input: SportsRequestInput): Promise<SportsSubscription> {
    const subscription = await requestSportsEvent(input);

    setEvents((current) =>
      current.map((event) =>
        event.provider === subscription.provider &&
        event.providerEventId === subscription.providerEventId
          ? {
              ...event,
              requested: true
            }
          : event
      )
    );

    return subscription;
  }

  return (
    <PortalPage
      accessDeniedDescription="Your Atlas account does not have permission to browse Sports events."
      description={
        sportsRoute.pageDescription ??
        "Browse upcoming supported sporting events and request one through Atlas."
      }
      eyebrow={sportsRoute.label}
      permission={sportsRoute.permission}
      title="Sports"
    >
      {loading ? (
        <section aria-busy="true" aria-label="Loading Sports events" className="requests-grid">
          <p>Loading upcoming Sports events…</p>
        </section>
      ) : error ? (
        <section aria-labelledby="sports-load-error-title" className="requests-message-panel">
          <p className="portal-page-eyebrow">Sports unavailable</p>

          <h2 id="sports-load-error-title">Atlas could not load Sports events</h2>

          <p>{error}</p>

          <button
            className="requests-refresh-button"
            onClick={() => {
              void load();
            }}
            type="button"
          >
            Retry
          </button>
        </section>
      ) : (
        <SportsRequestView events={events} onRequestEvent={handleRequestEvent} />
      )}
    </PortalPage>
  );
}
