"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";
import { loadDownloads } from "../api/downloads";
import type { DownloadsSnapshot, DownloadsState } from "../types/downloads";

export type UseDownloadsResult = Readonly<{
  state: DownloadsState;
  refresh: () => void;
}>;

function normalizeDownloadsError(value: unknown): Error {
  if (value instanceof Error) return value;
  return new Error("Unable to load Atlas download activity.");
}

export function useDownloads(): UseDownloadsResult {
  const { isAuthenticated } = useAuth();
  const [data, setData] = useState<DownloadsSnapshot | null>(null);
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
      return () => controller.abort();
    }

    void loadDownloads({ signal: controller.signal })
      .then((snapshot) => {
        if (controller.signal.aborted) return;
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
        setError(normalizeDownloadsError(requestError));
      });

    return () => controller.abort();
  }, [isAuthenticated, requestVersion]);

  const state = useMemo<DownloadsState>(() => {
    if (error !== null) return { status: "error", error };
    if (data === null) return { status: "loading" };
    return { status: "ready", data };
  }, [data, error]);

  return { state, refresh };
}
