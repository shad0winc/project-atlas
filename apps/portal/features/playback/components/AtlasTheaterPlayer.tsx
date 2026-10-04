"use client";

import { useEffect, useRef, useState } from "react";

import { DislikeAction } from "../../dislikes";
import { MediaRetentionStatus } from "../../media/components/MediaRetentionStatus";
import type { MediaRetention } from "../../media/types/retention";

import { resolvePlaybackSession } from "../services/session";
import type { SubtitleSelection } from "../services/session";
import { bootstrapPlaybackStream } from "../services/stream";
import { refreshPlaybackForRetry, retryResumePosition } from "../services/retry";
import { nextEpisodeTarget } from "../services/episode-navigation";
import { readResume, resumeKey, restoreContinuity, writeResume } from "../services/continuity";
import type { PlaybackSession, PlaybackTrack } from "../types/session";

type PlayerState =
  | Readonly<{ status: "connecting" }>
  | Readonly<{ status: "ready" }>
  | Readonly<{ status: "error"; message: string }>;

function subtitleOptionLabel(track: PlaybackTrack): string {
  const qualifiers = [track.default ? "Default" : "", track.forced ? "Forced" : ""].filter(Boolean);

  if (qualifiers.length === 0) {
    return track.label;
  }

  return `${track.label} (${qualifiers.join(", ")})`;
}

function subtitleSelectionValue(selection: SubtitleSelection): string {
  return typeof selection === "number" ? String(selection) : selection;
}

function parseSubtitleSelection(value: string): SubtitleSelection {
  if (value === "auto" || value === "off") {
    return value;
  }

  const index = Number(value);

  if (!Number.isInteger(index) || index < 0) {
    throw new Error("Invalid subtitle selection.");
  }

  return index;
}

type FavoriteState = "loading" | "idle" | "submitting" | "complete" | "unavailable";

export function AtlasTheaterPlayer({
  session,
  viewerId,
  onNextEpisode,
  autoAdvance = true,
  sessionResolver = resolvePlaybackSession,
  retention = null,
  canFavorite = false,
  favoriteState = "loading",
  onFavorite,
  canDislike = false,
  dislikeExpectedUserId,
  onDisliked
}: {
  session: PlaybackSession;
  viewerId?: string;
  onNextEpisode?: (itemId: string) => void;
  autoAdvance?: boolean;
  sessionResolver?: (
    provider: string,
    itemId: string,
    signal?: AbortSignal,
    subtitle?: SubtitleSelection
  ) => Promise<PlaybackSession>;
  retention?: MediaRetention | null;
  canFavorite?: boolean;
  favoriteState?: FavoriteState;
  onFavorite?: () => void | Promise<void>;
  canDislike?: boolean;
  dislikeExpectedUserId?: string;
  onDisliked?: () => void | Promise<void>;
}): React.ReactElement {
  const videoRef = useRef<HTMLVideoElement>(null);
  const resumeAtRef = useRef<number | null>(null);
  const shouldPlayRef = useRef(session.sourceType !== "live");
  const [autoplayBlocked, setAutoplayBlocked] = useState(false);
  const retryRequestRef = useRef<AbortController | null>(null);

  const [activeSession, setActiveSession] = useState<PlaybackSession>(session);

  const [subtitleSelection, setSubtitleSelection] = useState<SubtitleSelection>("auto");

  const [subtitleChanging, setSubtitleChanging] = useState(false);

  const [state, setState] = useState<PlayerState>({
    status: "connecting"
  });

  useEffect(() => () => retryRequestRef.current?.abort(), []);

  function rememberPlaybackPosition(): void {
    resumeAtRef.current = retryResumePosition(
      activeSession.canSeek,
      videoRef.current?.currentTime,
      resumeAtRef.current
    );
  }

  async function retryPlayback(): Promise<void> {
    if (retryRequestRef.current !== null) return;
    rememberPlaybackPosition();
    const controller = new AbortController();
    retryRequestRef.current = controller;
    setState({ status: "connecting" });
    try {
      const refreshed = await refreshPlaybackForRetry(
        activeSession,
        sessionResolver,
        subtitleSelection,
        controller.signal
      );
      setActiveSession(refreshed);
    } catch (error: unknown) {
      if (!controller.signal.aborted) {
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Atlas could not renew playback."
        });
      }
    } finally {
      if (retryRequestRef.current === controller) retryRequestRef.current = null;
    }
  }

  useEffect(() => {
    const video = videoRef.current;

    if (video === null) {
      return;
    }

    const controller = new AbortController();
    let disposed = false;
    let destroyHls: (() => void) | undefined;
    let sourceAttached = false;

    const key = resumeKey(viewerId, activeSession.provider, activeSession.playableTargetId,
      activeSession.canSeek && activeSession.sourceType !== "live");
    if (resumeAtRef.current === null && key) {
      try { resumeAtRef.current = readResume(window.localStorage, key); } catch { /* Optional storage. */ }
    }
    let restoring = false;
    let restored = false;
    let lastSaved = 0;
    setAutoplayBlocked(false);
    const savePosition = () => {
      if (!restored) return;
      try { writeResume(window.localStorage, key, video.currentTime, video.ended); } catch { /* Optional storage. */ }
    };
    const restorePlaybackPosition = async () => {
      if (disposed || !sourceAttached || restoring || restored) return;
      restoring = true;
      const result = await restoreContinuity(video, resumeAtRef.current, shouldPlayRef.current);
      restoring = false;
      if (disposed) return;
      if (result.restored) {
        restored = true;
        resumeAtRef.current = null;
        setAutoplayBlocked(result.blocked);
      }
    };
    const pausePlayback = () => {
      savePosition();
      if (restored && !disposed) shouldPlayRef.current = false;
    };
    const updatePosition = () => {
      void restorePlaybackPosition();
      if (Date.now() - lastSaved >= 5000) { savePosition(); lastSaved = Date.now(); }
    };
    for (const event of ["loadedmetadata", "canplay", "progress", "durationchange"]) {
      video.addEventListener(event, restorePlaybackPosition);
    }
    video.addEventListener("timeupdate", updatePosition);
    video.addEventListener("pause", pausePlayback);
    video.addEventListener("ended", savePosition);
    window.addEventListener("pagehide", savePosition);

    void bootstrapPlaybackStream(activeSession, controller.signal)
      .then(async ({ streamUrl }) => {
        if (disposed) {
          return;
        }

        const { default: Hls } = await import("hls.js");

        if (disposed) {
          return;
        }

        const nativeHls = video.canPlayType("application/vnd.apple.mpegurl");
        const managedHls = Hls.isSupported();

        // Prefer managed HLS for both library and live streams. Native HLS
        // remains the fallback when MediaSource playback is unavailable.
        if (nativeHls && !managedHls) {
          video.crossOrigin = "use-credentials";
          video.src = streamUrl;
          video.load();
          sourceAttached = true;
          setState({ status: "ready" });
          return;
        }

        if (!managedHls) {
          throw new Error("This browser cannot play the Jellyfin HLS stream.");
        }

        const hls = new Hls({
          xhrSetup(xhr) {
            xhr.withCredentials = true;
          }
        });

        destroyHls = () => hls.destroy();

        hls.on(Hls.Events.ERROR, (_event, data) => {
          if (!data.fatal || disposed) {
            return;
          }

          restored = false;
          resumeAtRef.current = retryResumePosition(
            activeSession.canSeek,
            video.currentTime,
            resumeAtRef.current
          );
          setState({
            status: "error",
            message: "Jellyfin playback encountered a fatal stream error."
          });

          hls.destroy();
        });

        hls.attachMedia(video);
        hls.loadSource(streamUrl);
        sourceAttached = true;

        setState({ status: "ready" });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || disposed) {
          return;
        }

        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Atlas could not start playback."
        });
      });

    return () => {
      disposed = true;
      controller.abort();
      destroyHls?.();

      savePosition();
      for (const event of ["loadedmetadata", "canplay", "progress", "durationchange"]) {
        video.removeEventListener(event, restorePlaybackPosition);
      }
      video.removeEventListener("timeupdate", updatePosition);
      video.removeEventListener("pause", pausePlayback);
      video.removeEventListener("ended", savePosition);
      window.removeEventListener("pagehide", savePosition);

      video.removeAttribute("src");
      video.load();
    };
  }, [activeSession, viewerId]);

  async function changeSubtitle(selection: SubtitleSelection): Promise<void> {
    const video = videoRef.current;

    if (video !== null && Number.isFinite(video.currentTime)) {
      resumeAtRef.current = retryResumePosition(activeSession.canSeek, video.currentTime, resumeAtRef.current);
      shouldPlayRef.current = !video.paused;
    }

    setSubtitleSelection(selection);
    setSubtitleChanging(true);
    setState({ status: "connecting" });

    try {
      const refreshed = await sessionResolver(
        activeSession.provider,
        activeSession.playableTargetId,
        undefined,
        selection
      );

      if (!refreshed.available) {
        throw new Error("Playback is not currently available.");
      }

      setActiveSession(refreshed);
    } catch (error: unknown) {
      setState({
        status: "error",
        message: error instanceof Error ? error.message : "Atlas could not change closed captions."
      });
    } finally {
      setSubtitleChanging(false);
    }
  }

  const hasSubtitleTracks = activeSession.subtitleTracks.length > 0;

  return (
    <div
      aria-label="Atlas embedded player"
      className="atlas-theater-player"
      data-playback-backend={activeSession.backend}
      data-playback-source={activeSession.sourceType}
      data-requested-target={activeSession.requestedTargetId}
      data-playable-target={activeSession.playableTargetId}
    >
      <div className="atlas-theater-video-shell">
        <video
          aria-label={`Playing ${activeSession.title}`}
          className="atlas-theater-video"
          controls
          onEnded={() => {
            const next = nextEpisodeTarget(activeSession, autoAdvance);
            if (next !== null) onNextEpisode?.(next);
          }}
          onPlay={() => { shouldPlayRef.current = true; setAutoplayBlocked(false); }}
          onError={() => {
            rememberPlaybackPosition();
            setState({
              status: "error",
              message: "The browser could not play this stream."
            });
          }}
          playsInline
          preload="metadata"
          ref={videoRef}
        />

        {state.status === "connecting" ? (
          <p className="atlas-theater-status" role="status">
            Establishing secure Jellyfin playback…
          </p>
        ) : null}

        {state.status === "error" ? (
          <div className="atlas-theater-status" role="alert">
            <p>{state.message}</p>
            <button
              className="button button-secondary"
              onClick={() => {
                void retryPlayback();
              }}
              type="button"
            >
              Retry playback
            </button>
          </div>
        ) : null}
      </div>

      <div className="atlas-theater-player-meta">
        <span>Powered by Jellyfin</span>
        {autoplayBlocked ? (
          <div role="status">
            <span>Playback is paused. </span>
            <button className="button button-secondary" type="button" onClick={() => {
              const video = videoRef.current;
              if (video) void video.play().then(() => setAutoplayBlocked(false)).catch(() => setAutoplayBlocked(true));
            }}>Play</button>
          </div>
        ) : null}

        {retention !== null ? <MediaRetentionStatus retention={retention} /> : null}

        {canFavorite && onFavorite !== undefined ? (
          <button
            aria-busy={favoriteState === "loading" || favoriteState === "submitting"}
            aria-label={
              favoriteState === "complete"
                ? `${activeSession.title} added to favorites`
                : favoriteState === "unavailable"
                  ? `Favorite state unavailable for ${activeSession.title}`
                  : `Add ${activeSession.title} to favorites`
            }
            className="media-discovery-primary-button"
            disabled={favoriteState !== "idle"}
            onClick={() => {
              void onFavorite();
            }}
            type="button"
          >
            {favoriteState === "complete"
              ? "Added to favorites"
              : favoriteState === "submitting"
                ? "Adding…"
                : favoriteState === "loading"
                  ? "Checking favorites…"
                  : favoriteState === "unavailable"
                    ? "Favorites unavailable"
                    : "Add to favorites"}
          </button>
        ) : null}

        {canDislike && dislikeExpectedUserId ? (
          <DislikeAction
            expectedUserId={dislikeExpectedUserId}
            itemId={activeSession.playableTargetId}
            onDisliked={onDisliked}
            provider={activeSession.provider}
            title={activeSession.title}
          />
        ) : null}

        {activeSession.canSeek ? <span>Seeking available</span> : null}

        {hasSubtitleTracks ? (
          <label>
            <span>Closed captions</span>{" "}
            <select
              aria-label="Closed captions"
              disabled={subtitleChanging || state.status === "connecting"}
              onChange={(event) => {
                void changeSubtitle(parseSubtitleSelection(event.currentTarget.value));
              }}
              value={subtitleSelectionValue(subtitleSelection)}
            >
              <option value="auto">Auto</option>
              <option value="off">Off</option>

              {activeSession.subtitleTracks.map((track) => (
                <option key={track.index} value={String(track.index)}>
                  {subtitleOptionLabel(track)}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span>Closed captions unavailable</span>
        )}

        {subtitleChanging ? <span role="status">Changing captions…</span> : null}
      </div>
    </div>
  );
}
