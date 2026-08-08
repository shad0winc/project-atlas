"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";

import { loadPortalDashboard } from "../api/portal-dashboard";

import type { PortalDashboardSnapshot } from "../types/portal-dashboard";

type PortalDashboardErrorState = Readonly<{
  message: string;
}>;

type PortalDashboardState =
  | Readonly<{
      status: "loading";
      data: null;
      error: null;
    }>
  | Readonly<{
      status: "success";
      data: PortalDashboardSnapshot;
      error: null;
    }>
  | Readonly<{
      status: "error";
      data: null;
      error: PortalDashboardErrorState;
    }>;

type UsePortalDashboardResult = Readonly<{
  state: PortalDashboardState;
  refresh: () => void;
}>;

function createErrorState(error: unknown): PortalDashboardErrorState {
  if (error instanceof Error && error.message.trim()) {
    return {
      message: error.message.trim()
    };
  }

  return {
    message: "Atlas could not load the portal dashboard."
  };
}

function createState(
  data: PortalDashboardSnapshot | null,
  error: PortalDashboardErrorState | null
): PortalDashboardState {
  if (error) {
    return {
      status: "error",
      data: null,
      error
    };
  }

  if (data) {
    return {
      status: "success",
      data,
      error: null
    };
  }

  return {
    status: "loading",
    data: null,
    error: null
  };
}

export function usePortalDashboard(): UsePortalDashboardResult {
  const { isAuthenticated } = useAuth();

  const [data, setData] = useState<PortalDashboardSnapshot | null>(null);

  const [error, setError] = useState<PortalDashboardErrorState | null>(null);

  const [requestVersion, setRequestVersion] = useState(0);

  const refresh = useCallback((): void => {
    setData(null);
    setError(null);
    setRequestVersion((current) => current + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    if (!isAuthenticated) {
      return () => {
        controller.abort();
      };
    }

    void loadPortalDashboard({
      signal: controller.signal
    })
      .then((dashboard) => {
        if (controller.signal.aborted) {
          return;
        }

        setData(dashboard);
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
        setError(createErrorState(requestError));
      });

    return () => {
      controller.abort();
    };
  }, [isAuthenticated, requestVersion]);

  return {
    state: useMemo(() => createState(data, error), [data, error]),
    refresh
  };
}
