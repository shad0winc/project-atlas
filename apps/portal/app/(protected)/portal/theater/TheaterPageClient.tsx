"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { loadPlaybackAction } from "../../../../features/playback/api/playback";

type TheaterState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "error"; message: string }>;

export function TheaterPageClient(): React.ReactElement {
  const searchParams = useSearchParams();
  const provider = searchParams.get("provider")?.trim() ?? "";
  const itemId = searchParams.get("item")?.trim() ?? "";

  const [state, setState] = useState<TheaterState>({
    status: "loading"
  });

  const hasValidTarget = Boolean(provider && itemId);

  useEffect(() => {
    if (!hasValidTarget) {
      return;
    }

    const controller = new AbortController();

    void loadPlaybackAction(provider, itemId, {
      signal: controller.signal
    })
      .then((action) => {
        if (!action.available || !action.href) {
          throw new Error("Playback is not currently available.");
        }

        window.location.replace(action.href);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        setState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "Atlas could not prepare playback."
        });
      });

    return () => {
      controller.abort();
    };
  }, [hasValidTarget, itemId, provider]);

  if (!hasValidTarget) {
    return (
      <section aria-labelledby="theater-error-title">
        <p className="portal-page-eyebrow">Theater</p>
        <h1 id="theater-error-title">Playback unavailable</h1>
        <p>Atlas Theater did not receive a valid playback target.</p>
        <Link href="/portal/media">Return to Media</Link>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section aria-labelledby="theater-error-title">
        <p className="portal-page-eyebrow">Theater</p>
        <h1 id="theater-error-title">Playback unavailable</h1>
        <p>{state.message}</p>
        <Link href="/portal/media">Return to Media</Link>
      </section>
    );
  }

  return (
    <section aria-busy="true" aria-labelledby="theater-loading-title">
      <p className="portal-page-eyebrow">Theater</p>
      <h1 id="theater-loading-title">Preparing playback</h1>
      <p>Atlas is opening the exact playable item.</p>
    </section>
  );
}
