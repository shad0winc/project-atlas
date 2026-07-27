"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";

import { loadMedia } from "../api/media";
import type { MediaSnapshot } from "../types/media";
import { createMediaState, type MediaState } from "../types/media-state";

export type UseMediaResult = Readonly<{
  state: MediaState;
  refresh: () => void;
}>;

function normalizeMediaError(value: unknown): Error {
  if (value instanceof Error) {
    return value;
  }

  return new Error("Unable to load Atlas media libraries.");
}

export function useMedia(): UseMediaResult {
  const { isAuthenticated } = useAuth();

  const [data, setData] = useState<MediaSnapshot | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  const refresh = useCallback((): void => {
    setData(null);
    setError(null);
    setRequestVersion((currentVersion) => currentVersion + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    if (!isAuthenticated) {
      return () => {
        controller.abort();
      };
    }

    void loadMedia({
      signal: controller.signal
    })
      .then((snapshot) => {
        if (controller.signal.aborted) {
          return;
        }

        setData(snapshot);
        setError(null);
      })
      .catch((requestError: unknown) => {
        if (
          controller.signal.aborted ||
          (requestError instanceof DOMException && requestError.name === "AbortError")
        ) {
          return;
        }

        setData(null);
        setError(normalizeMediaError(requestError));
      });

    return () => {
      controller.abort();
    };
  }, [isAuthenticated, requestVersion]);

  const state = useMemo(() => createMediaState(data, error), [data, error]);

  return {
    state,
    refresh
  };
}
