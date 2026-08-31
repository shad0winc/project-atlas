"use client";

import { useState } from "react";

import type {
  SportsEvent,
  SportsFollow,
  SportsSearchResult,
  SportsSubscription
} from "../types/sports";

export type SportsRequestInput = Readonly<{
  provider: string;
  providerEventId: string;
}>;

export type SportsRequestViewProps = Readonly<{
  events: readonly SportsEvent[];
  follows: readonly SportsFollow[];
  searchResults: readonly SportsSearchResult[];
  searchType: "team" | "league";
  onSearch: (type: "team" | "league", query: string) => Promise<void>;
  onFollow: (type: "team" | "league", providerId: string) => Promise<void>;
  onUnfollow: (subscriptionId: string) => Promise<void>;
  onBrowse: (type: "team" | "league", providerId: string) => Promise<void>;
  onRequestEvent: (input: SportsRequestInput) => Promise<SportsSubscription>;
  onSetRecording: (event: SportsEvent, record: boolean) => Promise<void>;
}>;

export function SportsRequestView({
  events,
  follows,
  searchResults,
  searchType,
  onSearch,
  onFollow,
  onUnfollow,
  onBrowse,
  onRequestEvent,
  onSetRecording
}: SportsRequestViewProps): React.ReactElement {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"team" | "league">("team");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function mutate(
    identity: string,
    action: () => Promise<unknown>
  ): Promise<void> {
    if (pending) {
      return;
    }

    setPending(identity);
    setError(null);

    try {
      await action();
    } catch (mutationError) {
      setError(
        mutationError instanceof Error
          ? mutationError.message
          : "Atlas could not update Sports."
      );
    } finally {
      setPending(null);
    }
  }

  return (
    <section aria-label="Sports discovery and following" className="requests-view">
      <div className="media-discovery-results-header">
        <div>
          <p className="portal-page-eyebrow">Discover</p>
          <h2>Find your Sports</h2>
          <p>Search teams or leagues, follow what matters to you, then browse upcoming events.</p>
        </div>
      </div>

      <form
        className="requests-search"
        onSubmit={(event) => {
          event.preventDefault();
          void mutate("search", () => onSearch(kind, query));
        }}
      >
        <label>
          Search type
          <select
            aria-label="Search type"
            onChange={(event) => setKind(event.target.value as "team" | "league")}
            value={kind}
          >
            <option value="team">Teams</option>
            <option value="league">Leagues</option>
          </select>
        </label>

        <label>
          Search Sports
          <input
            aria-label="Search Sports"
            onChange={(event) => setQuery(event.target.value)}
            placeholder={kind === "team" ? "Search teams" : "Search leagues"}
            value={query}
          />
        </label>

        <button
          className="requests-refresh-button"
          disabled={!query.trim() || pending === "search"}
          type="submit"
        >
          {pending === "search" ? "Searching..." : "Search"}
        </button>
      </form>

      {error ? (
        <section aria-live="polite" className="requests-mutation-error">
          <strong>Sports action failed</strong>
          <p>{error}</p>
        </section>
      ) : null}

      {searchResults.length > 0 ? (
        <section
          aria-label={`Sports ${searchType} search results`}
          className="requests-grid"
        >
          {searchResults.map((result) => {
            const existing = follows.find(
              (item) => item.type === searchType && item.providerId === result.id
            );
            const identity = `${searchType}:${result.id}`;

            return (
              <article className="request-card" key={identity}>
                <div className="request-card-header">
                  <div>
                    <p className="request-card-kind">
                      {result.sport || "Sports"}
                      {result.league ? ` - ${result.league}` : ""}
                    </p>
                    <h3>{result.name}</h3>
                  </div>
                </div>

                <button
                  className="requests-refresh-button"
                  onClick={() => {
                    void mutate(
                      `browse:${identity}`,
                      () => onBrowse(searchType, result.id)
                    );
                  }}
                  type="button"
                >
                  View upcoming
                </button>

                <button
                  className="requests-refresh-button"
                  disabled={pending === identity}
                  onClick={() => {
                    void mutate(
                      identity,
                      () =>
                        existing
                          ? onUnfollow(existing.subscriptionId)
                          : onFollow(searchType, result.id)
                    );
                  }}
                  type="button"
                >
                  {pending === identity ? "Updating..." : existing ? "Unfollow" : "Follow"}
                </button>
              </article>
            );
          })}
        </section>
      ) : null}

      <div className="media-discovery-results-header">
        <div>
          <p className="portal-page-eyebrow">Following</p>
          <h2>My Sports</h2>
          <p>Following keeps teams and leagues handy. It does not automatically record events.</p>
        </div>
      </div>

      {follows.length === 0 ? (
        <section className="requests-message-panel">
          <h3>You are not following any Sports yet</h3>
          <p>Use Discover above to follow a team or league.</p>
        </section>
      ) : (
        <section aria-label="Followed Sports" className="requests-grid">
          {follows.map((follow) => (
            <article className="request-card" key={follow.subscriptionId}>
              <div className="request-card-header">
                <div>
                  <p className="request-card-kind">{follow.type}</p>
                  <h3>{follow.name}</h3>
                </div>
                <span className="request-status">Following</span>
              </div>

              {follow.type === "team" || follow.type === "league" ? (
                <button
                  className="requests-refresh-button"
                  onClick={() => {
                    const browseType: "team" | "league" =
                      follow.type === "team"
                        ? "team"
                        : "league";

                    void mutate(
                      `browse:${follow.subscriptionId}`,
                      () => onBrowse(browseType, follow.providerId)
                    );
                  }}
                  type="button"
                >
                  View upcoming
                </button>
              ) : null}

              <button
                className="requests-refresh-button"
                onClick={() => {
                  void mutate(
                    follow.subscriptionId,
                    () => onUnfollow(follow.subscriptionId)
                  );
                }}
                type="button"
              >
                Unfollow
              </button>
            </article>
          ))}
        </section>
      )}

      <div className="media-discovery-results-header">
        <div>
          <p className="portal-page-eyebrow">Upcoming events</p>
          <h2>Sports</h2>
          <p>Request a supported event through Atlas. Following and recording remain separate.</p>
        </div>
      </div>

      {events.length === 0 ? (
        <section className="requests-message-panel">
          <p className="portal-page-eyebrow">No upcoming events</p>
          <h3>Atlas has no supported Sports events to show right now</h3>
          <p>Search for a team or league above, or check again as new events are discovered.</p>
        </section>
      ) : (
        <section aria-label="Upcoming Sports events" className="requests-grid">
          {events.map((event) => {
            const identity = `${event.provider}:${event.providerEventId}`;
            const pendingIdentity = `event:${identity}`;
            const recordingIdentity = `recording:${identity}`;
            const eventFollow = follows.find(
              (follow) =>
                follow.type === "event" &&
                follow.provider === event.provider &&
                follow.providerId === event.providerEventId
            );
            const recording = Boolean(eventFollow?.record);

            return (
              <article className="request-card" key={identity}>
                <div className="request-card-header">
                  <div>
                    <p className="request-card-kind">
                      {event.sport} - {event.league}
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
                  disabled={event.requested || pending === pendingIdentity}
                  onClick={() => {
                    void mutate(
                      pendingIdentity,
                      () =>
                        onRequestEvent({
                          provider: event.provider,
                          providerEventId: event.providerEventId
                        })
                    );
                  }}
                  type="button"
                >
                  {event.requested
                    ? "Requested"
                    : pending === pendingIdentity
                      ? "Requesting..."
                      : "Request event"}
                </button>


                <button
                  className="requests-refresh-button"
                  disabled={pending === recordingIdentity}
                  onClick={() => {
                    void mutate(
                      recordingIdentity,
                      () => onSetRecording(event, !recording)
                    );
                  }}
                  type="button"
                >
                  {pending === recordingIdentity
                    ? "Updating recording..."
                    : recording
                      ? "Cancel recording"
                      : "Record event"}
                </button>
              </article>
            );
          })}
        </section>
      )}
    </section>
  );
}
