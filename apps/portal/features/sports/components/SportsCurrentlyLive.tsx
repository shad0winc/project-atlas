"use client";
import type { SportsEvent } from "../types/sports";
import type { SportsLiveAvailability } from "../services/sports";
import { sportsLocalStart } from "../services/currentlyLive";

export function SportsCurrentlyLive({
  events,
  availability,
  unavailable,
  onWatchLive,
  scopeLabel,
}: Readonly<{
  events: readonly SportsEvent[];
  availability: Readonly<Record<string, SportsLiveAvailability>>;
  unavailable: boolean;
  scopeLabel?: string;
  onWatchLive: (channelId: string) => Promise<void>;
}>): React.ReactElement {
  return (
    <section
      aria-labelledby="sports-currently-live"
      className="requests-message-panel"
    >
      <h2 id="sports-currently-live">Currently Live</h2>
      <p>
        {scopeLabel
          ? `Provider-reported live events for ${scopeLabel}.`
          : "Provider-reported live events from your followed teams, leagues, and events."}
        {" "}Start times use your device timezone. Channels appear here only when their current program is verified.
      </p>
      {unavailable ? (
        <p role="status">
          Some live event information is temporarily unavailable.
        </p>
      ) : null}
      {events.length === 0 ? (
        <p>{scopeLabel
          ? `No events for ${scopeLabel} are currently verified live.`
          : "No followed events are currently verified live."}</p>
      ) : (
        <div className="requests-grid">
          {events.map((event) => {
            const channel =
              availability[`${event.provider}:${event.providerEventId}`];
            const channelId = channel?.available
              ? channel.atlasChannelId
              : null;
            return (
              <article
                className="request-card"
                key={`${event.provider}:${event.providerEventId}`}
              >
                <h3>{event.name}</h3>
                <p>{event.league}</p>
                <p>
                  Started{" "}
                  <time dateTime={event.startAt}>
                    {sportsLocalStart(event.startAt)}
                  </time>
                </p>
                {channelId ? (
                  <button
                    type="button"
                    className="requests-refresh-button"
                    onClick={() => {
                      void onWatchLive(channelId);
                    }}
                  >
                    Watch Live
                  </button>
                ) : (
                  <p>Live playback is not currently available.</p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
