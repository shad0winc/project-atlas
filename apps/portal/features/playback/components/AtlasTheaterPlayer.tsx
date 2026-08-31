"use client";

import { useEffect, useRef, useState } from "react";

import { bootstrapPlaybackStream } from "../services/stream";
import type { PlaybackSession } from "../types/session";

type PlayerState =
  | Readonly<{ status: "connecting" }>
  | Readonly<{ status: "ready" }>
  | Readonly<{ status: "error"; message: string }>;

export function AtlasTheaterPlayer({
  session
}: {
  session: PlaybackSession;
}): React.ReactElement {
  const videoRef = useRef<HTMLVideoElement>(null);
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

    setState({ status: "connecting" });

    void bootstrapPlaybackStream(session, controller.signal)
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
            message: "Jellyfin playback encountered a fatal stream error."
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
      video.removeAttribute("src");
      video.load();
    };
  }, [attempt, session]);

  return (
    <div
      aria-label="Atlas embedded player"
      className="atlas-theater-player"
      data-playback-backend={session.backend}
      data-playback-source={session.sourceType}
      data-requested-target={session.requestedTargetId}
      data-playable-target={session.playableTargetId}
    >
      <div className="atlas-theater-video-shell">
        <video
          aria-label={`Playing ${session.title}`}
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
              onClick={() => setAttempt((value) => value + 1)}
              type="button"
            >
              Retry playback
            </button>
          </div>
        ) : null}
      </div>

      <div className="atlas-theater-player-meta">
        <span>Powered by Jellyfin</span>
        {session.canSeek ? <span>Seeking available</span> : null}
      </div>
    </div>
  );
}
