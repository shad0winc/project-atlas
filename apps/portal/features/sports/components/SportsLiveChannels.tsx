"use client";

import { useEffect, useState } from "react";
import {
  loadSportsLiveChannels,
  type SportsLiveChannel,
} from "../services/liveChannels";

export function SportsLiveChannels({
  onWatchLive,
}: Readonly<{
  onWatchLive: (atlasChannelId: string) => Promise<void>;
}>): React.ReactElement {
  const [channels, setChannels] = useState<readonly SportsLiveChannel[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [opening, setOpening] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void loadSportsLiveChannels(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setChannels(result);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("Live channels are temporarily unavailable.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [refresh]);

  const normalizedQuery = query.trim().toLocaleLowerCase().replace(/\s+/g, "");
  const visible = channels.filter((channel) =>
    channel.name
      .toLocaleLowerCase()
      .replace(/\s+/g, "")
      .includes(normalizedQuery),
  );

  async function watch(channel: SportsLiveChannel): Promise<void> {
    if (opening !== null) return;
    setOpening(channel.atlasChannelId);
    try {
      await onWatchLive(channel.atlasChannelId);
    } catch {
      setError("Atlas could not start live playback. Please try again.");
    } finally {
      setOpening(null);
    }
  }

  return (
    <section
      aria-labelledby="sports-live-channels-title"
      className="requests-message-panel"
    >
      <h2 id="sports-live-channels-title">Live channels</h2>
      <p>Watch broadcasts such as RedZone. Scheduled games appear in Events.</p>
      <div className="requests-toolbar">
        <label htmlFor="sports-live-channel-search">Search live channels</label>
        <input
          id="sports-live-channel-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button
          type="button"
          className="requests-refresh-button"
          disabled={loading}
          onClick={() => {
            setLoading(true);
            setError(null);
            setRefresh((value) => value + 1);
          }}
        >
          Refresh live channels
        </button>
      </div>
      {loading ? (
        <p role="status">Loading live channels...</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : visible.length === 0 ? (
        <p>
          {channels.length === 0
            ? "No live channels are configured yet."
            : "No live channels match your search."}
        </p>
      ) : (
        <ul>
          {visible.map((channel) => (
            <li key={channel.atlasChannelId}>
              <strong>{channel.name}</strong>{" "}
              {channel.playbackConfigured ? (
                <button
                  type="button"
                  disabled={opening !== null}
                  onClick={() => {
                    void watch(channel);
                  }}
                >
                  {opening === channel.atlasChannelId
                    ? "Opening..."
                    : "Watch Live"}
                </button>
              ) : (
                <span>Playback setup pending</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
