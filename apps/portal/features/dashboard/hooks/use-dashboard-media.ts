"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";

import { loadDashboardMedia } from "../api/dashboard-media";
import type { DashboardMediaSnapshot } from "../types/dashboard-media";

type DashboardMediaLoadingState = Readonly<{
  status: "loading";
}>;

type DashboardMediaReadyState = Readonly<{
  status: "ready";
  data: DashboardMediaSnapshot;
}>;

type DashboardMediaErrorState = Readonly<{
  status: "error";
  error: Error;
}>;

export type DashboardMediaState =
  DashboardMediaLoadingState | DashboardMediaReadyState | DashboardMediaErrorState;

export type UseDashboardMediaResult = Readonly<{
  state: DashboardMediaState;
  refresh: () => void;
}>;

function normalizeError(value: unknown): Error {
  if (value instanceof Error) {
    return value;
  }

  return new Error("Unable to load Atlas media statistics.");
}

export function useDashboardMedia(): UseDashboardMediaResult {
  const { isAuthenticated } = useAuth();

  const [data, setData] = useState<DashboardMediaSnapshot | null>(null);
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

    void loadDashboardMedia({
      signal: controller.signal
    })
      .then((dashboardMedia) => {
        if (controller.signal.aborted) {
          return;
        }

        setData(dashboardMedia);
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
        setError(normalizeError(requestError));
      });

    return () => {
      controller.abort();
    };
  }, [isAuthenticated, requestVersion]);

  const state = useMemo((): DashboardMediaState => {
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
    refresh
  };
}
