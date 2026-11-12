"use client";

import { useEffect, useRef, useState } from "react";

import { DislikeAction } from "../../dislikes";
import { MediaRetentionStatus } from "../../media/components/MediaRetentionStatus";
import type { MediaRetention } from "../../media/types/retention";
import { refreshAtlasAuthAccessToken, subscribeAtlasAuthLifecycle } from "../../../lib/auth/session-lifecycle";
import { readAtlasAuthSession } from "../../../lib/auth/storage";

import { resolvePlaybackSession } from "../services/session";
import type { SubtitleSelection } from "../services/session";
import { bootstrapPlaybackStream } from "../services/stream";
import { adminPlaybackRefreshDelay, refreshPlaybackForRetry, retryResumePosition } from "../services/retry";
import { createPlaybackDiagnostics } from "../services/diagnostics";
import { captionStartupPolicy } from "../services/caption-startup";
import { safeLiveSeekPosition } from "../services/live-seek";
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

function adminAccessToken(viewerId: string | undefined): string | null {
  const login = readAtlasAuthSession();
  if (!login || login.user.user_id !== viewerId ||
      !login.user.roles.some((role) => role === "admin" || role === "global_admin")) return null;
  return login.tokens.accessToken;
}

export function AtlasTheaterPlayer({
  session,
  viewerId,
  onNextEpisode,
  autoAdvance = true,
  sessionResolver = resolvePlaybackSession,
  liveSessionRenewer,
  retention = null,
  canFavorite = false,
  favoriteState = "loading",
  onFavorite,
  canDislike = false,
  dislikeExpectedUserId,
  onDisliked,
  onTerminalError
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
  liveSessionRenewer?: (signal: AbortSignal) => Promise<PlaybackSession>;
  retention?: MediaRetention | null;
  canFavorite?: boolean;
  favoriteState?: FavoriteState;
  onFavorite?: () => void | Promise<void>;
  canDislike?: boolean;
  dislikeExpectedUserId?: string;
  onDisliked?: () => void | Promise<void>;
  onTerminalError?: (failedSession: PlaybackSession) => void;
}): React.ReactElement {
  const videoRef = useRef<HTMLVideoElement>(null);
  const terminalErrorRef = useRef(onTerminalError);
  useEffect(() => { terminalErrorRef.current = onTerminalError; }, [onTerminalError]);
  const resumeAtRef = useRef<number | null>(null);
  const shouldPlayRef = useRef(true);
  const [autoplayBlocked, setAutoplayBlocked] = useState(false);
  const retryRequestRef = useRef<AbortController | null>(null);
  const streamUrlRef = useRef<string | null>(null);
  const sessionResolverRef = useRef(sessionResolver);
  useEffect(() => { sessionResolverRef.current = sessionResolver; }, [sessionResolver]);

  const [activeSession, setActiveSession] = useState<PlaybackSession>(session);

  const [subtitleSelection, setSubtitleSelection] = useState<SubtitleSelection>("auto");

  const [subtitleChanging, setSubtitleChanging] = useState(false);
  const [captionError, setCaptionError] = useState(false);
  const previousCaptionSelectionRef = useRef<SubtitleSelection | null>(null);
  const captionStartupRef = useRef(false);
  const [captionPreparing, setCaptionPreparing] = useState(false);

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
    const previousCaptionSelection = previousCaptionSelectionRef.current;
    const retrySelection = previousCaptionSelection ?? subtitleSelection;
    rememberPlaybackPosition();
    const controller = new AbortController();
    retryRequestRef.current = controller;
    setState({ status: "connecting" });
    try {
      const token = adminAccessToken(viewerId);
      if (activeSession.sourceType === "library" && token && adminPlaybackRefreshDelay(token) === 0) {
        await refreshAtlasAuthAccessToken();
      }
      const refreshed = await refreshPlaybackForRetry(
        activeSession,
        sessionResolver,
        retrySelection,
        controller.signal
      );
      if (previousCaptionSelection !== null) {
        previousCaptionSelectionRef.current = null;
        captionStartupRef.current = false;
        setCaptionError(false);
        setSubtitleSelection(previousCaptionSelection);
      }
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
    const streamUrl = streamUrlRef.current;
    const initialToken = adminAccessToken(viewerId);
    const live = activeSession.sourceType === "live";
    if (state.status !== "ready" || subtitleChanging || (live && !liveSessionRenewer) ||
        !streamUrl || !initialToken) return;

    const videoScope = new URL(streamUrl).pathname.split("/")[2];
    const controller = new AbortController();
    const { signal } = controller;
    let boundToken = initialToken;
    let timer: number | undefined;
    let renewing = false;

    function schedule() {
      window.clearTimeout(timer);
      const delay = adminPlaybackRefreshDelay(boundToken);
      if (delay !== null) timer = window.setTimeout(() => void renew(), delay);
    }

    async function renew() {
      if (signal.aborted || renewing || retryRequestRef.current) return;
      renewing = true;
      window.clearTimeout(timer);
      try {
        const current = adminAccessToken(viewerId);
        if (!current) return;
        const token = current === boundToken
          ? await refreshAtlasAuthAccessToken()
          : current;
        signal.throwIfAborted();
        if (!adminAccessToken(viewerId)) throw new Error("Administrator access ended.");
        const refreshed = live && liveSessionRenewer
          ? await liveSessionRenewer(signal)
          : await refreshPlaybackForRetry(activeSession, sessionResolverRef.current, subtitleSelection, signal);
        signal.throwIfAborted();
        const renewed = await bootstrapPlaybackStream(refreshed, signal);
        signal.throwIfAborted();
        const scopeChanged = live
          ? renewed.streamUrl !== streamUrl
          : new URL(renewed.streamUrl).pathname.split("/")[2] !== videoScope;
        if (scopeChanged) {
          throw new Error("The playback scope changed during renewal.");
        }
        boundToken = token;
        schedule();
      } catch {
        if (!signal.aborted) {
          setState({ status: "error", message: "Atlas could not renew secure playback. Try again." });
        }
      } finally {
        renewing = false;
      }
    }

    const unsubscribe = subscribeAtlasAuthLifecycle({ onRefreshSucceeded: () => void renew() });
    schedule();
    return () => {
      unsubscribe();
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [activeSession, liveSessionRenewer, state.status, subtitleChanging, subtitleSelection, viewerId]);

  useEffect(() => {
    const video = videoRef.current;

    if (video === null) {
      return;
    }

    const controller = new AbortController();
    let disposed = false;
    let terminalErrorReported = false;
    let destroyHls: (() => void) | undefined;
    let sourceAttached = false;

    const key = resumeKey(viewerId, activeSession.provider, activeSession.playableTargetId,
      activeSession.canSeek && activeSession.sourceType !== "live");
    if (resumeAtRef.current === null && key) {
      try { resumeAtRef.current = readResume(window.localStorage, key); } catch { /* Optional storage. */ }
    }
    let restoring = false;
    let restored = false;
    let nativeCaptionStartup = false;
    const confirmNativeCaptions = () => {
      if (!disposed && nativeCaptionStartup) {
        nativeCaptionStartup = false;
        previousCaptionSelectionRef.current = null;
        captionStartupRef.current = false;
      }
    };
    video.addEventListener("canplay", confirmNativeCaptions);
    let lastSaved = 0;
    let lastLivePosition: number | null = null;
    setAutoplayBlocked(false);
    const savePosition = () => {
      if (!restored) return;
      try {
        writeResume(window.localStorage, key, video.currentTime, video.ended, {
          title: activeSession.title,
          duration: Number.isFinite(video.duration) ? video.duration : undefined,
          episode: activeSession.mediaType === "tv" || Boolean(activeSession.seriesId)
        });
      } catch { /* Optional storage. */ }
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
    const guardLiveSeek = () => {
      if (disposed || activeSession.sourceType !== "live") return;
      const target = safeLiveSeekPosition(video, video.currentTime) ?? lastLivePosition;
      if (target !== null && Math.abs(video.currentTime - target) > 0.05) {
        try { video.currentTime = target; } catch { /* The live window may be moving. */ }
      }
    };
    const updatePosition = () => {
      if (activeSession.sourceType === "live" && !video.seeking && Number.isFinite(video.currentTime)) {
        lastLivePosition = video.currentTime;
      }
      void restorePlaybackPosition();
      if (Date.now() - lastSaved >= 5000) { savePosition(); lastSaved = Date.now(); }
    };
    for (const event of ["loadedmetadata", "canplay", "progress", "durationchange"]) {
      video.addEventListener(event, restorePlaybackPosition);
    }
    video.addEventListener("timeupdate", updatePosition);
    video.addEventListener("seeking", guardLiveSeek);
    video.addEventListener("pause", pausePlayback);
    video.addEventListener("ended", savePosition);
    window.addEventListener("pagehide", savePosition);

    void bootstrapPlaybackStream(activeSession, controller.signal)
      .then(async ({ streamUrl }) => {
        if (disposed) {
          return;
        }
        streamUrlRef.current = streamUrl;

        const { default: Hls } = await import("hls.js");

        if (disposed) {
          return;
        }

        const nativeHls = video.canPlayType("application/vnd.apple.mpegurl");
        const managedHls = Hls.isSupported();

        // Prefer managed HLS for both library and live streams. Native HLS
        // remains the fallback when MediaSource playback is unavailable.
        if (nativeHls && !managedHls) {
          nativeCaptionStartup = previousCaptionSelectionRef.current !== null;
          setCaptionPreparing(false);
          video.crossOrigin = "use-credentials";
          video.src = streamUrl;
          video.load();
          sourceAttached = true;
          if (activeSession.sourceType === "live") void restorePlaybackPosition();
          setState({ status: "ready" });
          return;
        }

        if (!managedHls) {
          throw new Error("This browser cannot play the Jellyfin HLS stream.");
        }

        const normalFragmentPolicy = Hls.DefaultConfig?.fragLoadPolicy?.default;
        const captionStartup = activeSession.sourceType === "library" &&
          captionStartupRef.current && normalFragmentPolicy !== undefined;
        const hls = new Hls({
          ...(captionStartup ? {
            fragLoadPolicy: { default: captionStartupPolicy(normalFragmentPolicy) }
          } : {}),
          xhrSetup(xhr) {
            xhr.withCredentials = true;
          }
        });

        destroyHls = () => hls.destroy();
        setCaptionPreparing(captionStartup);

        const diagnostic = createPlaybackDiagnostics(video);
        hls.on(Hls.Events.FRAG_LOADED, (_event, data) => {
          if (!disposed && captionStartup && data.frag.type === "main") {
            hls.config.fragLoadPolicy.default = normalFragmentPolicy;
            captionStartupRef.current = false;
            setCaptionPreparing(false);
          }
          diagnostic("fragment_loaded", { fragmentSequence: data.frag.sn,
            fragmentStart: data.frag.start, fragmentDuration: data.frag.duration });
        });
        hls.on(Hls.Events.FRAG_BUFFERED, (_event, data) => {
          if (!disposed && !terminalErrorReported && data.frag.type === "main") {
            previousCaptionSelectionRef.current = null;
          }
          if (activeSession.sourceType === "live" && data.frag.type === "main") {
            void restorePlaybackPosition();
          }
          diagnostic("fragment_buffered", { fragmentSequence: data.frag.sn,
            fragmentStart: data.frag.start, fragmentDuration: data.frag.duration });
        });
        hls.on(Hls.Events.ERROR, (_event, data) => {
          diagnostic("hls_error", { type: data.type, details: data.details,
            fatal: data.fatal, responseStatus: data.response?.code,
            fragmentSequence: data.frag?.sn, fragmentStart: data.frag?.start,
            fragmentDuration: data.frag?.duration });
          if (!data.fatal || disposed || terminalErrorReported) {
            return;
          }

          terminalErrorReported = true;
          setCaptionPreparing(false);
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
          terminalErrorRef.current?.(activeSession);
        });

        hls.attachMedia(video);
        hls.loadSource(streamUrl);
        sourceAttached = true;
        if (activeSession.sourceType === "live") void restorePlaybackPosition();

        setState({ status: "ready" });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || disposed) {
          return;
        }

        setCaptionPreparing(false);
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Atlas could not start playback."
        });
      });

    return () => {
      disposed = true;
      streamUrlRef.current = null;
      controller.abort();
      savePosition();
      for (const event of ["loadedmetadata", "canplay", "progress", "durationchange"]) {
        video.removeEventListener(event, restorePlaybackPosition);
      }
      video.removeEventListener("canplay", confirmNativeCaptions);
      video.removeEventListener("timeupdate", updatePosition);
      video.removeEventListener("seeking", guardLiveSeek);
      video.removeEventListener("pause", pausePlayback);
      video.removeEventListener("ended", savePosition);
      window.removeEventListener("pagehide", savePosition);

      destroyHls?.();
      video.removeAttribute("src");
      video.load();
    };
  }, [activeSession, viewerId]);

  async function changeSubtitle(selection: SubtitleSelection): Promise<void> {
    setCaptionError(false);
    setSubtitleChanging(true);

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

      const video = videoRef.current;
      if (video !== null && Number.isFinite(video.currentTime)) {
        rememberPlaybackPosition();
        shouldPlayRef.current = !video.paused;
      }
      const startsLibraryCaptions = refreshed.sourceType === "library" && typeof selection === "number";
      previousCaptionSelectionRef.current = startsLibraryCaptions
        ? previousCaptionSelectionRef.current ?? subtitleSelection
        : null;
      captionStartupRef.current = startsLibraryCaptions;
      setSubtitleSelection(selection);
      setState({ status: "connecting" });
      setActiveSession(refreshed);
    } catch {
      setCaptionError(true);
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
              {previousCaptionSelectionRef.current === null
                ? "Retry playback"
                : "Resume with previous captions"}
            </button>
          </div>
        ) : null}
      </div>

      <div className="atlas-theater-player-meta">
        <span>Powered by Jellyfin</span>
        {activeSession.sourceType === "live" ? (
          <span>Live seeking keeps a seven-second buffer.</span>
        ) : null}
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
              disabled={subtitleChanging || captionPreparing || state.status === "connecting"}
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

        {captionError ? <span role="alert">Atlas could not change closed captions. The previous selection is still active.</span> : null}
        {subtitleChanging ? <span role="status">Changing captions…</span> : null}
        {captionPreparing ? <span role="status">Preparing captions…</span> : null}
      </div>
    </div>
  );
}
