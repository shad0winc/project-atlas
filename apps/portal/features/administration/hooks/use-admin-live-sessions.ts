"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../../lib/auth/use-auth";
import {
  clearAdminLiveSessionUserOverride,
  loadAdminLiveSessionPolicy,
  setAdminLiveSessionUserOverride,
  updateAdminLiveSessionDefault,
  type AdminLiveSessionPolicy
} from "../api/live-sessions";

export type AdminLiveSessionsState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "error"; error: Error }>
  | Readonly<{ status: "ready"; policy: AdminLiveSessionPolicy }>;

function normalizeError(value: unknown, fallback: string): Error {
  return value instanceof Error ? value : new Error(fallback);
}

export function useAdminLiveSessions(enabled = true) {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState<AdminLiveSessionsState>({ status: "loading" });
  const [requestVersion, setRequestVersion] = useState(0);
  const [mutationError, setMutationError] = useState<Error | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setMutationError(null);
    setState({ status: "loading" });
    setRequestVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    if (!isAuthenticated || !enabled) return () => controller.abort();

    loadAdminLiveSessionPolicy(controller.signal)
      .then((policy) => {
        if (!controller.signal.aborted) setState({ status: "ready", policy });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) return;
        setState({
          status: "error",
          error: normalizeError(error, "Unable to load Live-session administration.")
        });
      });

    return () => controller.abort();
  }, [enabled, isAuthenticated, requestVersion]);

  const setDefaultLimit = useCallback(async (limit: number): Promise<boolean> => {
    setBusyKey("default");
    setMutationError(null);
    try {
      await updateAdminLiveSessionDefault(limit);
      refresh();
      return true;
    } catch (error: unknown) {
      setMutationError(normalizeError(error, "Unable to update the default Live-session limit."));
      return false;
    } finally {
      setBusyKey(null);
    }
  }, [refresh]);

  const setUserOverride = useCallback(async (userId: string, limit: number): Promise<boolean> => {
    setBusyKey(`user:${userId}`);
    setMutationError(null);
    try {
      await setAdminLiveSessionUserOverride(userId, limit);
      refresh();
      return true;
    } catch (error: unknown) {
      setMutationError(normalizeError(error, "Unable to update this user's Live-session limit."));
      return false;
    } finally {
      setBusyKey(null);
    }
  }, [refresh]);

  const clearUserOverride = useCallback(async (userId: string): Promise<boolean> => {
    setBusyKey(`user:${userId}`);
    setMutationError(null);
    try {
      await clearAdminLiveSessionUserOverride(userId);
      refresh();
      return true;
    } catch (error: unknown) {
      setMutationError(normalizeError(error, "Unable to return this user to the default limit."));
      return false;
    } finally {
      setBusyKey(null);
    }
  }, [refresh]);

  return {
    state,
    refresh,
    mutationError,
    busyKey,
    setDefaultLimit,
    setUserOverride,
    clearUserOverride
  };
}
