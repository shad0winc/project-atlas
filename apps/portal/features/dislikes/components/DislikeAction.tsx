"use client";

import { useState } from "react";

import { addDislike } from "../api/dislikes";

export type DislikeActionProps = Readonly<{
  provider: string;
  itemId: string;
  expectedUserId: string;
  title?: string;
}>;

type DislikeActionState =
  | "idle"
  | "submitting"
  | "complete";

export function DislikeAction({
  provider,
  itemId,
  expectedUserId,
  title
}: DislikeActionProps): React.ReactElement {
  const [state, setState] =
    useState<DislikeActionState>("idle");

  const [error, setError] =
    useState<string | null>(null);

  const displayTitle =
    title?.trim() || "this item";

  const isSubmitting =
    state === "submitting";

  const isComplete =
    state === "complete";

  async function handleDislike(): Promise<void> {
    if (isSubmitting || isComplete) {
      return;
    }

    setState("submitting");
    setError(null);

    try {
      await addDislike(
        {
          provider,
          itemId
        },
        {
          expectedUserId
        }
      );

      setState("complete");
    } catch {
      setState("idle");
      setError(
        `Atlas could not mark ${displayTitle} as disliked.`
      );
    }
  }

  return (
    <span>
      <button
        aria-busy={isSubmitting}
        aria-label={
          isComplete
            ? `${displayTitle} disliked; cleanup eligible after 24 hours`
            : `Dislike ${displayTitle}; schedule cleanup after 24 hours`
        }
        className="media-discovery-secondary-button"
        disabled={isSubmitting || isComplete}
        onClick={() => {
          void handleDislike();
        }}
        type="button"
      >
        {isComplete
          ? "Disliked · delete after 24h"
          : isSubmitting
            ? "Disliking…"
            : "Dislike 👎"}
      </button>

      {error !== null ? (
        <span aria-live="polite" role="alert">
          {error}
        </span>
      ) : null}
    </span>
  );
}
