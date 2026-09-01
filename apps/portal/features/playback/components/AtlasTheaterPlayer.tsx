"use client";

import { useEffect, useRef, useState } from "react";

import { resolvePlaybackSession } from "../services/session";
import type { SubtitleSelection } from "../services/session";
import { bootstrapPlaybackStream } from "../services/stream";
import type { PlaybackSession, PlaybackTrack } from "../types/session";

type PlayerState =
  | Readonly<{ status: "connecting" }>
  | Readonly<{ status: "ready" }>
  | Readonly<{ status: "error"; message: string }>;

function subtitleOptionLabel(track: PlaybackTrack): string {
  const qualifiers = [
    track.default ? "Default" : "",
    track.forced ? "Forced" : ""
  ].filter(Boolean);

  if (qualifiers.length === 0) {
    return track.label;
  }

  return `${track.label} (${qualifiers.join(", ")})`;
}

function subtitleSelectionValue(
  selection: SubtitleSelection
): string {
  return typeof selection === "number"
    ? String(selection)
    : selection;
}

function parseSubtitleSelection(
  value: string
): SubtitleSelection {
  if (value === "auto" || value === "off") {
    return value;
  }

  const index = Number(value);

  if (!Number.isInteger(index) || index < 0) {
    throw new Error("Invalid subtitle selection.");
  }

  return index;
}

export function AtlasTheaterPlayer({
  session
}: {
  session: PlaybackSession;
}): React.ReactElement {
  const videoRef = useRef<HTMLVideoElement>(null);
  const resumeAtRef = useRef<number | null>(null);

  const [activeSession, setActiveSession] =
    useState<PlaybackSession>(session);

  const [subtitleSelection, setSubtitleSelection] =
    useState<SubtitleSelection>("auto");

  const [subtitleChanging, setSubtitleChanging] =
    useState(false);

  const [attempt, setAttempt] = useState(0);

  const [state, setState] = useState<PlayerState>({
    status: "connecting"
  });

  useEffect(() => {
    const video = videoRef.current;

    if (video === null) {
      return;
    }

    const controller = new AbortController();
    let disposed = false;
    let destroyHls: (() => void) | undefined;

    const restorePlaybackPosition = () => {
      const resumeAt = resumeAtRef.current;

      if (
        resumeAt === null ||
        !Number.isFinite(resumeAt) ||
        resumeAt <= 0
      ) {
        return;
      }

      try {
        video.currentTime = resumeAt;
      } catch {
        // The browser may reject seeking until a later media event.
        return;
      }

      resumeAtRef.current = null;
    };

    video.addEventListener(
      "loadedmetadata",
      restorePlaybackPosition
    );

    void bootstrapPlaybackStream(activeSession, controller.signal)
      .then(async ({ streamUrl }) => {
        if (disposed) {
          return;
        }

        const nativeHls = video.canPlayType(
          "application/vnd.apple.mpegurl"
        );

        if (nativeHls) {
          video.crossOrigin = "use-credentials";
          video.src = streamUrl;
          video.load();
          setState({ status: "ready" });
          return;
        }

        const { default: Hls } = await import("hls.js");

        if (disposed) {
          return;
        }

        if (!Hls.isSupported()) {
          throw new Error(
            "This browser cannot play the Jellyfin HLS stream."
          );
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

          setState({
            status: "error",
            message:
              "Jellyfin playback encountered a fatal stream error."
          });

          hls.destroy();
        });

        hls.attachMedia(video);
        hls.loadSource(streamUrl);

        setState({ status: "ready" });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || disposed) {
          return;
        }

        setState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "Atlas could not start playback."
        });
      });

    return () => {
      disposed = true;
      controller.abort();
      destroyHls?.();

      video.removeEventListener(
        "loadedmetadata",
        restorePlaybackPosition
      );

      video.removeAttribute("src");
      video.load();
    };
  }, [activeSession, attempt]);

  async function changeSubtitle(
    selection: SubtitleSelection
  ): Promise<void> {
    const video = videoRef.current;

    if (video !== null && Number.isFinite(video.currentTime)) {
      resumeAtRef.current = video.currentTime;
    }

    setSubtitleSelection(selection);
    setSubtitleChanging(true);
    setState({ status: "connecting" });

    try {
      const refreshed = await resolvePlaybackSession(
        activeSession.provider,
        activeSession.requestedTargetId,
        undefined,
        selection
      );

      if (!refreshed.available) {
        throw new Error(
          "Playback is not currently available."
        );
      }

      setActiveSession(refreshed);
    } catch (error: unknown) {
      setState({
        status: "error",
        message:
          error instanceof Error
            ? error.message
            : "Atlas could not change closed captions."
      });
    } finally {
      setSubtitleChanging(false);
    }
  }

  const hasSubtitleTracks =
    activeSession.subtitleTracks.length > 0;

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
          onError={() => {
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
                setState({ status: "connecting" });
                setAttempt((value) => value + 1);
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

        {activeSession.canSeek ? (
          <span>Seeking available</span>
        ) : null}

        {hasSubtitleTracks ? (
          <label>
            <span>Closed captions</span>{" "}
            <select
              aria-label="Closed captions"
              disabled={subtitleChanging}
              onChange={(event) => {
                void changeSubtitle(
                  parseSubtitleSelection(
                    event.currentTarget.value
                  )
                );
              }}
              value={subtitleSelectionValue(
                subtitleSelection
              )}
            >
              <option value="auto">Auto</option>
              <option value="off">Off</option>

              {activeSession.subtitleTracks.map((track) => (
                <option
                  key={track.index}
                  value={String(track.index)}
                >
                  {subtitleOptionLabel(track)}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span>Closed captions unavailable</span>
        )}

        {subtitleChanging ? (
          <span role="status">Changing captions…</span>
        ) : null}
      </div>
    </div>
  );
}
