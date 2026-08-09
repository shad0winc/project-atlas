"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";

import { loadMediaDiscovery, loadMediaSearch } from "../api/discovery";
import {
  normalizeMediaDiscoveryPageNumber,
  normalizeMediaDiscoveryQuery,
  normalizeMediaDiscoveryType,
  type MediaDiscoveryMediaType,
  type MediaDiscoveryPage
} from "../types/discovery";

export type MediaDiscoveryMode = "discover" | "search";

export type MediaDiscoveryLoadingState = Readonly<{
  status: "loading";
}>;

export type MediaDiscoveryReadyState = Readonly<{
  status: "ready";
  data: MediaDiscoveryPage;
}>;

export type MediaDiscoveryErrorState = Readonly<{
  status: "error";
  error: Error;
}>;

export type MediaDiscoveryState =
  MediaDiscoveryLoadingState | MediaDiscoveryReadyState | MediaDiscoveryErrorState;

export type UseMediaDiscoveryResult = Readonly<{
  state: MediaDiscoveryState;
  mode: MediaDiscoveryMode;
  mediaType: MediaDiscoveryMediaType;
  activeQuery: string;
  browse: (mediaType: MediaDiscoveryMediaType) => void;
  search: (query: string) => void;
  goToPage: (page: number) => void;
  refresh: () => void;
}>;

function normalizeDiscoveryError(value: unknown): Error {
  if (value instanceof Error) {
    return value;
  }

  return new Error("Unable to load Atlas media discovery.");
}

export function useMediaDiscovery(): UseMediaDiscoveryResult {
  const { isAuthenticated } = useAuth();

  const [mode, setMode] = useState<MediaDiscoveryMode>("discover");
  const [mediaType, setMediaType] = useState<MediaDiscoveryMediaType>("movie");
  const [activeQuery, setActiveQuery] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<MediaDiscoveryPage | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  const beginRead = useCallback((): void => {
    setData(null);
    setError(null);
    setRequestVersion((currentVersion) => currentVersion + 1);
  }, []);

  const browse = useCallback(
    (nextMediaType: MediaDiscoveryMediaType): void => {
      setMode("discover");
      setMediaType(normalizeMediaDiscoveryType(nextMediaType));
      setActiveQuery("");
      setPage(1);
      beginRead();
    },
    [beginRead]
  );

  const search = useCallback(
    (query: string): void => {
      setMode("search");
      setActiveQuery(normalizeMediaDiscoveryQuery(query));
      setPage(1);
      beginRead();
    },
    [beginRead]
  );

  const goToPage = useCallback(
    (nextPage: number): void => {
      setPage(normalizeMediaDiscoveryPageNumber(nextPage));
      beginRead();
    },
    [beginRead]
  );

  const refresh = useCallback((): void => {
    beginRead();
  }, [beginRead]);

  useEffect(() => {
    const controller = new AbortController();

    if (!isAuthenticated) {
      return () => {
        controller.abort();
      };
    }

    const request =
      mode === "search"
        ? loadMediaSearch({
            query: activeQuery,
            page,
            signal: controller.signal
          })
        : loadMediaDiscovery({
            mediaType,
            page,
            signal: controller.signal
          });

    void request
      .then((nextPage) => {
        if (controller.signal.aborted) {
          return;
        }

        setData(nextPage);
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
        setError(normalizeDiscoveryError(requestError));
      });

    return () => {
      controller.abort();
    };
  }, [activeQuery, isAuthenticated, mediaType, mode, page, requestVersion]);

  const state = useMemo<MediaDiscoveryState>(() => {
    if (error) {
      return {
        status: "error",
        error
      };
    }

    if (data) {
      return {
        status: "ready",
        data
      };
    }

    return {
      status: "loading"
    };
  }, [data, error]);

  return {
    state,
    mode,
    mediaType,
    activeQuery,
    browse,
    search,
    goToPage,
    refresh
  };
}
