"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";

import { cancelMediaRequest, loadRequests } from "../api/requests";

import { RequestCancellationError } from "../services/requests";

import {
  createRequestsState,
  replaceMediaRequest,
  type MediaRequest,
  type RequestsState
} from "../types/requests";

export type RequestMutationFailure = Readonly<{
  requestId: string;
  error: Error;
  reconciliationRequired: boolean;
}>;

export type UseRequestsResult = Readonly<{
  state: RequestsState;
  refresh: () => void;
  cancelRequest: (requestId: string) => Promise<boolean>;
  cancellingRequestId: string | null;
  blockedCancellationIds: readonly string[];
  mutationFailure: RequestMutationFailure | null;
}>;

type RequestsLoadResult = Readonly<{
  userId: string;
  data: readonly MediaRequest[] | null;
  error: Error | null;
}>;

function normalizeRequestError(value: unknown, fallback: string): Error {
  if (value instanceof Error) {
    return value;
  }

  return new Error(fallback);
}

function appendUnique(values: readonly string[], value: string): readonly string[] {
  if (values.includes(value)) {
    return values;
  }

  return [...values, value];
}

export function useRequests(): UseRequestsResult {
  const { isAuthenticated, user } = useAuth();

  const currentUserId = user?.user_id ?? null;

  const [loadResult, setLoadResult] = useState<RequestsLoadResult | null>(null);

  const [requestVersion, setRequestVersion] = useState(0);

  const [cancellingRequestId, setCancellingRequestId] = useState<string | null>(null);

  const [blockedCancellationIds, setBlockedCancellationIds] = useState<readonly string[]>([]);

  const [mutationFailure, setMutationFailure] = useState<RequestMutationFailure | null>(null);

  const refresh = useCallback((): void => {
    setLoadResult(null);
    setMutationFailure(null);

    setRequestVersion((currentVersion) => currentVersion + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    if (!isAuthenticated || !currentUserId) {
      return () => {
        controller.abort();
      };
    }

    void loadRequests({
      expectedUserId: currentUserId,
      signal: controller.signal
    })
      .then((requests) => {
        if (controller.signal.aborted) {
          return;
        }

        setLoadResult({
          userId: currentUserId,
          data: requests,
          error: null
        });

        // GET is observational and safe. A successful refresh confirms the
        // latest Atlas state and permits eligible actions to be reconsidered.
        setBlockedCancellationIds([]);
        setMutationFailure(null);
      })
      .catch((requestError: unknown) => {
        if (
          controller.signal.aborted ||
          (requestError instanceof DOMException && requestError.name === "AbortError")
        ) {
          return;
        }

        setLoadResult({
          userId: currentUserId,
          data: null,
          error: normalizeRequestError(requestError, "Unable to load your Atlas requests.")
        });
      });

    return () => {
      controller.abort();
    };
  }, [currentUserId, isAuthenticated, requestVersion]);

  const state = useMemo(() => {
    if (!currentUserId || loadResult?.userId !== currentUserId) {
      return createRequestsState(null, null);
    }

    return createRequestsState(loadResult.data, loadResult.error);
  }, [currentUserId, loadResult]);

  const cancelRequest = useCallback(
    async (requestId: string): Promise<boolean> => {
      if (!isAuthenticated || !currentUserId) {
        setMutationFailure({
          requestId,
          error: new Error("Atlas authentication session is unavailable."),
          reconciliationRequired: false
        });

        return false;
      }

      if (blockedCancellationIds.includes(requestId)) {
        setMutationFailure({
          requestId,
          error: new Error("Refresh request status before attempting another cancellation."),
          reconciliationRequired: false
        });

        return false;
      }

      setCancellingRequestId(requestId);

      setMutationFailure(null);

      try {
        const cancelled = await cancelMediaRequest(requestId, {
          expectedUserId: currentUserId
        });

        setLoadResult((current) => {
          if (current?.userId !== currentUserId || current.data === null) {
            return current;
          }

          return {
            userId: currentUserId,
            data: replaceMediaRequest(current.data, cancelled, currentUserId),
            error: null
          };
        });

        setBlockedCancellationIds((current) =>
          current.filter((identifier) => identifier !== requestId)
        );

        return true;
      } catch (requestError: unknown) {
        const error = normalizeRequestError(
          requestError,
          "Atlas did not confirm this cancellation."
        );

        setBlockedCancellationIds((current) => appendUnique(current, requestId));

        setMutationFailure({
          requestId,
          error,
          reconciliationRequired:
            requestError instanceof RequestCancellationError && requestError.reconciliationRequired
        });

        return false;
      } finally {
        setCancellingRequestId(null);
      }
    },
    [blockedCancellationIds, currentUserId, isAuthenticated]
  );

  return {
    state,
    refresh,
    cancelRequest,
    cancellingRequestId,
    blockedCancellationIds,
    mutationFailure
  };
}
