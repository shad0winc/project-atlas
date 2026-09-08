"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createAdminSportsProviderAccount,
  loadAdminSportsAccountConnection,
  loadAdminSportsProviders,
  loadAdminSportsResourcePool,
  removeAdminSportsProviderAccount,
  replaceAdminSportsAccountCredentials,
  testAdminSportsAccountConnection,
  updateAdminSportsAccount,
  updateAdminSportsProvider,
  type AdminSportsConnection,
  type AdminSportsConnectionTest,
  type AdminSportsProvider,
  type AdminSportsResourcePool,
  type CreateAdminSportsProviderAccountInput,
  type UpdateAdminSportsAccountInput,
  type UpdateAdminSportsCredentialsInput
} from "../api/provider-accounts";

export type AdminSportsProviderState =
  | Readonly<{
      status: "loading";
    }>
  | Readonly<{
      status: "error";
      error: Error;
    }>
  | Readonly<{
      status: "ready";
      providers: readonly AdminSportsProvider[];
      resourcePool: AdminSportsResourcePool;
    }>;

function normalizeError(error: unknown, fallback: string): Error {
  if (error instanceof Error && error.message.trim() !== "") {
    return error;
  }

  return new Error(fallback);
}

export function useAdminSportsProviders(enabled: boolean) {
  const [state, setState] = useState<AdminSportsProviderState>({
    status: "loading"
  });
  const [requestVersion, setRequestVersion] = useState(0);

  const [mutationError, setMutationError] = useState<Error | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const [connections, setConnections] = useState<Readonly<Record<string, AdminSportsConnection>>>(
    {}
  );

  const [connectionTests, setConnectionTests] = useState<
    Readonly<Record<string, AdminSportsConnectionTest>>
  >({});

  const refresh = useCallback((): void => {
    if (!enabled) return;

    setMutationError(null);
    setState({
      status: "loading"
    });
    setRequestVersion((value) => value + 1);
  }, [enabled]);

  useEffect(() => {
    let cancelled = false;

    if (!enabled) {
      return () => {
        cancelled = true;
      };
    }

    Promise.all([loadAdminSportsProviders(), loadAdminSportsResourcePool()])
      .then(([providers, resourcePool]) => {
        if (cancelled) return;

        setState({
          status: "ready",
          providers,
          resourcePool
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;

        setState({
          status: "error",
          error: normalizeError(error, "Sports provider administration is unavailable.")
        });
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, requestVersion]);

  const runAction = useCallback(
    async (
      key: string,
      fallback: string,
      action: () => Promise<void>,
      refreshAfter = false
    ): Promise<boolean> => {
      setBusyKey(key);
      setMutationError(null);

      try {
        await action();

        if (refreshAfter) {
          void refresh();
        }

        return true;
      } catch (error: unknown) {
        setMutationError(normalizeError(error, fallback));
        return false;
      } finally {
        setBusyKey(null);
      }
    },
    [refresh]
  );

  const renameProvider = useCallback(
    async (providerId: string, displayName: string): Promise<boolean> =>
      runAction(
        `provider:${providerId}:rename`,
        "Unable to rename this Sports provider.",
        async () => {
          await updateAdminSportsProvider(providerId, displayName);
        },
        true
      ),
    [runAction]
  );

  const updateAccount = useCallback(
    async (
      providerId: string,
      sourceId: string,
      input: UpdateAdminSportsAccountInput
    ): Promise<boolean> =>
      runAction(
        `account:${sourceId}:metadata`,
        "Unable to update this Sports provider account.",
        async () => {
          await updateAdminSportsAccount(providerId, sourceId, input);
        },
        true
      ),
    [runAction]
  );

  const setAccountEnabled = useCallback(
    async (providerId: string, sourceId: string, enabledValue: boolean): Promise<boolean> =>
      runAction(
        `account:${sourceId}:enabled`,
        enabledValue
          ? "Unable to enable this Sports provider account."
          : "Unable to disable this Sports provider account.",
        async () => {
          await updateAdminSportsAccount(providerId, sourceId, {
            enabled: enabledValue
          });
        },
        true
      ),
    [runAction]
  );

  const loadConnection = useCallback(
    async (providerId: string, sourceId: string): Promise<boolean> =>
      runAction(
        `account:${sourceId}:connection`,
        "Unable to read this provider connection configuration.",
        async () => {
          const connection = await loadAdminSportsAccountConnection(providerId, sourceId);

          setConnections((current) => ({
            ...current,
            [sourceId]: connection
          }));
        }
      ),
    [runAction]
  );

  const testConnection = useCallback(
    async (providerId: string, sourceId: string): Promise<boolean> =>
      runAction(
        `account:${sourceId}:test`,
        "Unable to test this Sports provider connection.",
        async () => {
          const result = await testAdminSportsAccountConnection(providerId, sourceId);

          setConnectionTests((current) => ({
            ...current,
            [sourceId]: result
          }));
        }
      ),
    [runAction]
  );

  const replaceCredentials = useCallback(
    async (
      providerId: string,
      sourceId: string,
      input: UpdateAdminSportsCredentialsInput
    ): Promise<boolean> =>
      runAction(
        `account:${sourceId}:credentials`,
        "Unable to replace this Sports provider connection.",
        async () => {
          const connection = await replaceAdminSportsAccountCredentials(
            providerId,
            sourceId,
            input
          );

          setConnections((current) => ({
            ...current,
            [sourceId]: connection
          }));

          setConnectionTests((current) => {
            const next = { ...current };
            delete next[sourceId];
            return next;
          });
        },
        true
      ),
    [runAction]
  );

  const createAccount = useCallback(
    async (providerId: string, input: CreateAdminSportsProviderAccountInput): Promise<boolean> =>
      runAction(
        "account:create",
        "Unable to create this Sports provider account.",
        async () => {
          await createAdminSportsProviderAccount(providerId, input);
        },
        true
      ),
    [runAction]
  );

  const removeAccount = useCallback(
    async (providerId: string, sourceId: string): Promise<boolean> =>
      runAction(
        `account:${sourceId}:remove`,
        "Unable to remove this Sports provider account.",
        async () => {
          await removeAdminSportsProviderAccount(providerId, sourceId);

          setConnections((current) => {
            const next = { ...current };
            delete next[sourceId];
            return next;
          });

          setConnectionTests((current) => {
            const next = { ...current };
            delete next[sourceId];
            return next;
          });
        },
        true
      ),
    [runAction]
  );

  return {
    state,
    refresh,
    mutationError,
    busyKey,
    connections,
    connectionTests,
    renameProvider,
    updateAccount,
    setAccountEnabled,
    loadConnection,
    testConnection,
    replaceCredentials,
    createAccount,
    removeAccount
  };
}
