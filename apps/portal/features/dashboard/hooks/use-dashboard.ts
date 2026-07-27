"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";

import { loadDashboard } from "../api/dashboard";
import type { DashboardSnapshot } from "../types/dashboard";
import {
  createDashboardErrorState,
  createDashboardState,
  type DashboardErrorState,
  type DashboardState
} from "../types/dashboard-state";

type UseDashboardResult = Readonly<{
  state: DashboardState;
  refresh: () => void;
}>;

export function useDashboard(): UseDashboardResult {
  const { isAuthenticated } = useAuth();

  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<DashboardErrorState | null>(null);
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

    void loadDashboard({
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
        setError(createDashboardErrorState(requestError));
      });

    return () => {
      controller.abort();
    };
  }, [isAuthenticated, requestVersion]);

  const state = useMemo(() => createDashboardState(data, error), [data, error]);

  return {
    state,
    refresh
  };
}
