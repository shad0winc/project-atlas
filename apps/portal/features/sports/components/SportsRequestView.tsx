"use client";

import { useState } from "react";

import type { SportsEvent, SportsSubscription } from "../types/sports";

export type SportsRequestInput = Readonly<{
  provider: string;
  providerEventId: string;
}>;

export type SportsRequestViewProps = Readonly<{
  events: readonly SportsEvent[];
  onRequestEvent: (input: SportsRequestInput) => Promise<SportsSubscription>;
}>;

export function SportsRequestView({
  events,
  onRequestEvent
}: SportsRequestViewProps): React.ReactElement {
  const [requestedEventIds, setRequestedEventIds] = useState<ReadonlySet<string>>(
    () =>
      new Set(
        events
          .filter((event) => event.requested)
          .map((event) => `${event.provider}:${event.providerEventId}`)
      )
  );

  const [pendingEventIds, setPendingEventIds] = useState<ReadonlySet<string>>(() => new Set());

  const [error, setError] = useState<string | null>(null);

  async function requestEvent(event: SportsEvent): Promise<void> {
    const identity = `${event.provider}:${event.providerEventId}`;

    if (requestedEventIds.has(identity) || pendingEventIds.has(identity)) {
      return;
    }

    setError(null);

    setPendingEventIds((current) => {
      const next = new Set(current);
      next.add(identity);
      return next;
    });

    try {
      await onRequestEvent({
        provider: event.provider,
        providerEventId: event.providerEventId
      });

      setRequestedEventIds((current) => {
        const next = new Set(current);
        next.add(identity);
        return next;
      });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Atlas could not request this Sports event."
      );
    } finally {
      setPendingEventIds((current) => {
        const next = new Set(current);
        next.delete(identity);
        return next;
      });
    }
  }

  return (
    <section aria-labelledby="sports-events-title" className="requests-view">
      <div className="media-discovery-results-header">
        <div>
          <p className="portal-page-eyebrow">Upcoming events</p>

          <h2 id="sports-events-title">Sports</h2>

          <p>Request one supported sporting event through Atlas.</p>
        </div>
      </div>

      {error ? (
        <section aria-live="polite" className="requests-mutation-error">
          <strong>Sports request failed</strong>

          <p>{error}</p>
        </section>
      ) : null}

      {events.length === 0 ? (
        <section className="requests-message-panel">
          <p className="portal-page-eyebrow">No upcoming events</p>

          <h3>Atlas has no supported Sports events to show right now</h3>

          <p>Check again after the configured Sports provider discovers new events.</p>
        </section>
      ) : (
        <section aria-label="Upcoming Sports events" className="requests-grid">
          {events.map((event) => {
            const identity = `${event.provider}:${event.providerEventId}`;

            const requested = event.requested || requestedEventIds.has(identity);

            const pending = pendingEventIds.has(identity);

            return (
              <article className="request-card" key={identity}>
                <div className="request-card-header">
                  <div>
                    <p className="request-card-kind">
                      {event.sport}
                      {" · "}
                      {event.league}
                    </p>

                    <h3>{event.name}</h3>
                  </div>

                  <span className="request-status">{event.status}</span>
                </div>

                <dl className="request-card-details">
                  <div>
                    <dt>Starts</dt>
                    <dd>{new Date(event.startAt).toLocaleString()}</dd>
                  </div>

                  <div>
                    <dt>Provider</dt>
                    <dd>{event.provider}</dd>
                  </div>
                </dl>

                <button
                  className="requests-refresh-button"
                  data-provider={event.provider}
                  data-provider-event-id={event.providerEventId}
                  disabled={requested || pending}
                  onClick={() => {
                    void requestEvent(event);
                  }}
                  type="button"
                >
                  {requested ? "Requested" : pending ? "Requesting…" : "Request event"}
                </button>
              </article>
            );
          })}
        </section>
      )}
    </section>
  );
}
