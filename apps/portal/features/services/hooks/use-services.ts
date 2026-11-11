"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "../../../lib/auth/use-auth";

import {
  loadManagedServiceDetail,
  loadServiceLifecycleOverview,
  loadServiceUpdateReport,
  scanServiceUpdates
} from "../api/services";
import {
  mergeManagedServiceDetail,
  type ManagedServiceDetail,
  type ServiceDetailState,
  type ServiceLifecycleSnapshot,
  type ServiceLifecycleState
} from "../types/services";

export type UpdateCheckStatus = "idle" | "checking" | "complete" | "error";

export type UseServicesResult = Readonly<{
  state: ServiceLifecycleState;
  detailState: ServiceDetailState;
  refresh: () => void;
  reloadObservations: () => void;
  checkForUpdates: () => void;
  updateCheckStatus: UpdateCheckStatus;
  selectService: (identifier: string) => void;
  clearSelection: () => void;
}>;

function normalizeServiceError(value: unknown): Error {
  if (value instanceof Error) {
    return value;
  }

  return new Error("Unable to load Atlas managed services.");
}

export function useServices(): UseServicesResult {
  const { isAuthenticated, user } = useAuth();
  const canRunMaintenance = user?.roles.includes("global_admin") === true;

  const [data, setData] = useState<ServiceLifecycleSnapshot | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  const [detail, setDetail] = useState<ManagedServiceDetail | null>(null);
  const [detailError, setDetailError] = useState<Error | null>(null);
  const [selectedIdentifier, setSelectedIdentifier] = useState<string | null>(null);

  const [updateCheckStatus, setUpdateCheckStatus] = useState<UpdateCheckStatus>("idle");
  const updateController = useRef<AbortController | null>(null);
  const detailController = useRef<AbortController | null>(null);
  const observationController = useRef<AbortController | null>(null);

  const refresh = useCallback((): void => {
    setData(null);
    setError(null);
    setRequestVersion((currentVersion) => currentVersion + 1);
  }, []);

  const reloadObservations = useCallback((): void => {
    if (!isAuthenticated) {
      return;
    }
    observationController.current?.abort();
    const controller = new AbortController();
    observationController.current = controller;
    void loadServiceLifecycleOverview({ signal: controller.signal })
      .then((snapshot) => {
        if (!controller.signal.aborted) {
          setData(snapshot);
        }
      })
      .catch(() => undefined);
  }, [isAuthenticated]);

  const checkForUpdates = useCallback((): void => {
    if (!isAuthenticated || updateController.current) {
      return;
    }

    const controller = new AbortController();
    updateController.current = controller;
    setUpdateCheckStatus("checking");

    const report = canRunMaintenance
      ? scanServiceUpdates(controller.signal).then(() =>
          loadServiceLifecycleOverview({ signal: controller.signal })
        )
      : loadServiceUpdateReport({ signal: controller.signal });

    void report
      .then((report) => {
        if (!controller.signal.aborted) {
          setData((snapshot) => {
            if ("services" in report) {
              return report;
            }
            return snapshot ? { ...snapshot, updates: report } : snapshot;
          });
          setUpdateCheckStatus("complete");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setUpdateCheckStatus("error");
        }
      })
      .finally(() => {
        if (updateController.current === controller) {
          updateController.current = null;
        }
      });
  }, [isAuthenticated, canRunMaintenance]);

  useEffect(
    () => () => {
      updateController.current?.abort();
      updateController.current = null;
      observationController.current?.abort();
      observationController.current = null;
    },
    [isAuthenticated]
  );

  const clearSelection = useCallback((): void => {
    detailController.current?.abort();
    detailController.current = null;
    setSelectedIdentifier(null);
    setDetail(null);
    setDetailError(null);
  }, []);

  const selectService = useCallback(
    (identifier: string): void => {
      const normalizedIdentifier = identifier.trim();

      if (!normalizedIdentifier) {
        return;
      }

      detailController.current?.abort();

      const controller = new AbortController();
      detailController.current = controller;

      setSelectedIdentifier(normalizedIdentifier);
      setDetail(null);
      setDetailError(null);

      void loadManagedServiceDetail(normalizedIdentifier, {
        signal: controller.signal
      })
        .then((managedService) => {
          if (controller.signal.aborted) {
            return;
          }

          const overviewService = data?.services.find(
            (service) => service.identifier === managedService.service.identifier
          );

          setDetail(mergeManagedServiceDetail(managedService, overviewService));
          setDetailError(null);
        })
        .catch((requestError: unknown) => {
          if (
            controller.signal.aborted ||
            (requestError instanceof DOMException && requestError.name === "AbortError")
          ) {
            return;
          }

          setDetail(null);
          setDetailError(normalizeServiceError(requestError));
        });
    },
    [data]
  );

  useEffect(() => {
    const controller = new AbortController();

    if (!isAuthenticated) {
      return () => {
        controller.abort();
      };
    }

    void loadServiceLifecycleOverview({
      signal: controller.signal
    })
      .then((snapshot) => {
        if (controller.signal.aborted) {
          return;
        }

        setData(snapshot);
        setError(null);
        setUpdateCheckStatus("idle");
      })
      .catch((requestError: unknown) => {
        if (
          controller.signal.aborted ||
          (requestError instanceof DOMException && requestError.name === "AbortError")
        ) {
          return;
        }

        setData(null);
        setError(normalizeServiceError(requestError));
      });

    return () => {
      controller.abort();
    };
  }, [isAuthenticated, requestVersion]);

  useEffect(
    () => () => {
      detailController.current?.abort();
    },
    []
  );

  const state = useMemo<ServiceLifecycleState>(() => {
    if (error !== null) {
      return {
        status: "error",
        error
      };
    }

    if (data === null) {
      return {
        status: "loading"
      };
    }

    return {
      status: "ready",
      data
    };
  }, [data, error]);

  const detailState = useMemo<ServiceDetailState>(() => {
    if (selectedIdentifier === null) {
      return {
        status: "idle"
      };
    }

    if (detailError !== null) {
      return {
        status: "error",
        identifier: selectedIdentifier,
        error: detailError
      };
    }

    if (detail === null) {
      return {
        status: "loading",
        identifier: selectedIdentifier
      };
    }

    return {
      status: "ready",
      data: detail
    };
  }, [detail, detailError, selectedIdentifier]);

  return {
    state,
    detailState,
    refresh,
    checkForUpdates,
    reloadObservations,
    updateCheckStatus,
    selectService,
    clearSelection
  };
}
