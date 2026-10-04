"use client";

import { useEffect, useRef, useState } from "react";
import {
  loadSportsLiveChannels,
  type SportsLiveChannel,
} from "../services/liveChannels";
import {
  followSports,
  loadSportsFollows,
  unfollowSports,
} from "../services/sports";
import type { SportsFollow } from "../types/sports";

export function SportsLiveChannels({
  onWatchLive,
}: Readonly<{
  onWatchLive: (atlasChannelId: string) => Promise<void>;
}>): React.ReactElement {
  const [channels, setChannels] = useState<readonly SportsLiveChannel[]>([]);
  const [follows, setFollows] = useState<readonly SportsFollow[]>([]);
  const [query, setQuery] = useState("");
  const [savedOnly, setSavedOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [opening, setOpening] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const saveLock = useRef(false);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      loadSportsLiveChannels(controller.signal),
      loadSportsFollows({ signal: controller.signal }),
    ])
      .then(([catalog, subscriptions]) => {
        if (!controller.signal.aborted) {
          setChannels(catalog);
          setFollows(
            subscriptions.filter(
              (follow) =>
                follow.type === "channel" && follow.provider === "atlas",
            ),
          );
        }
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            "Live channels and saved follows are temporarily unavailable.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [refresh]);

  const saved = new Map(follows.map((follow) => [follow.providerId, follow]));
  // Keep a saved channel removable even if it leaves the current catalog.
  const catalogIds = new Set(channels.map((channel) => channel.atlasChannelId));
  const combined = [
    ...channels,
    ...follows
      .filter((follow) => !catalogIds.has(follow.providerId))
      .map((follow) => ({
        atlasChannelId: follow.providerId,
        name: follow.name,
        playbackConfigured: false,
      })),
  ];
  const normalizedQuery = query.trim().toLocaleLowerCase().replace(/\s+/g, "");
  const visible = combined.filter(
    (channel) =>
      (!savedOnly || saved.has(channel.atlasChannelId)) &&
      channel.name
        .toLocaleLowerCase()
        .replace(/\s+/g, "")
        .includes(normalizedQuery),
  );

  async function toggleFollow(channel: SportsLiveChannel): Promise<void> {
    if (saveLock.current) return;
    saveLock.current = true;
    setSaving(channel.atlasChannelId);
    setActionError(null);
    const existing = saved.get(channel.atlasChannelId);
    try {
      if (existing) {
        await unfollowSports(existing.subscriptionId);
        if (mounted.current)
          setFollows((current) =>
            current.filter(
              (follow) => follow.subscriptionId !== existing.subscriptionId,
            ),
          );
      } else {
        const follow = await followSports("channel", channel.atlasChannelId);
        if (mounted.current)
          setFollows((current) => [
            ...current.filter((item) => item.providerId !== follow.providerId),
            follow,
          ]);
      }
    } catch {
      if (mounted.current)
        setActionError(
          "Atlas could not update your channel follow. Refresh to check its saved state before trying again.",
        );
    } finally {
      saveLock.current = false;
      if (mounted.current) setSaving(null);
    }
  }

  async function watch(channel: SportsLiveChannel): Promise<void> {
    if (opening !== null) return;
    setOpening(channel.atlasChannelId);
    setActionError(null);
    try {
      await onWatchLive(channel.atlasChannelId);
    } catch {
      if (mounted.current)
        setActionError(
          "Atlas could not start live playback. Please try again.",
        );
    } finally {
      if (mounted.current) setOpening(null);
    }
  }

  return (
    <section
      aria-labelledby="sports-live-channels-title"
      className="requests-message-panel"
    >
      <h2 id="sports-live-channels-title">Live channels</h2>
      <p>
        Follow channels to save your favorites here. Scheduled games appear in
        Events.
      </p>
      <div className="requests-toolbar">
        <label htmlFor="sports-live-channel-search">Search live channels</label>
        <input
          id="sports-live-channel-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label>
          <input
            type="checkbox"
            checked={savedOnly}
            onChange={(event) => setSavedOnly(event.target.checked)}
          />
          Followed channels only
        </label>
        <button
          type="button"
          className="requests-refresh-button"
          disabled={loading || saving !== null}
          onClick={() => {
            setLoading(true);
            setError(null);
            setActionError(null);
            setRefresh((value) => value + 1);
          }}
        >
          Refresh live channels
        </button>
      </div>
      {actionError ? <p role="alert">{actionError}</p> : null}
      {loading ? (
        <p role="status">Loading live channels...</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : visible.length === 0 ? (
        <p>
          {normalizedQuery
            ? "No live channels match your search."
            : savedOnly
              ? "You are not following any live channels yet."
              : "No live channels are configured yet."}
        </p>
      ) : (
        <ul>
          {visible.map((channel) => (
            <li key={channel.atlasChannelId}>
              <strong>{channel.name}</strong>{" "}
              <button
                type="button"
                aria-label={`${saved.has(channel.atlasChannelId) ? "Unfollow" : "Follow"} ${channel.name}`}
                disabled={saving !== null}
                onClick={() => {
                  void toggleFollow(channel);
                }}
              >
                {saving === channel.atlasChannelId
                  ? "Saving..."
                  : saved.has(channel.atlasChannelId)
                    ? "Unfollow"
                    : "Follow"}
              </button>{" "}
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
                <span>
                  {catalogIds.has(channel.atlasChannelId)
                    ? "Playback setup pending"
                    : "Channel currently unavailable"}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
