"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../../lib/auth/use-auth";
import {
  createAdminRole,
  deleteAdminRole,
  loadAdminRoleCatalog,
  updateAdminRole,
  type AdminRoleCatalog,
  type AdminRoleCreateInput,
  type AdminRoleUpdateInput
} from "../api/roles";

export type AdminRolesState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "error"; error: Error }>
  | Readonly<{ status: "ready"; catalog: AdminRoleCatalog }>;

function normalizeError(value: unknown, fallback: string): Error {
  return value instanceof Error ? value : new Error(fallback);
}

export function useAdminRoles(enabled = true) {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState<AdminRolesState>({ status: "loading" });
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
    loadAdminRoleCatalog(controller.signal)
      .then((catalog) => {
        if (!controller.signal.aborted) setState({ status: "ready", catalog });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return;
        setState({ status: "error", error: normalizeError(error, "Unable to load Atlas roles and permissions.") });
      });
    return () => controller.abort();
  }, [enabled, isAuthenticated, requestVersion]);

  const createRole = useCallback(async (input: AdminRoleCreateInput): Promise<boolean> => {
    setBusyKey("role:create"); setMutationError(null);
    try { await createAdminRole(input); refresh(); return true; }
    catch (error: unknown) { setMutationError(normalizeError(error, "Unable to create this Atlas role.")); return false; }
    finally { setBusyKey(null); }
  }, [refresh]);

  const updateRole = useCallback(async (name: string, input: AdminRoleUpdateInput): Promise<boolean> => {
    setBusyKey(`role:${name}`); setMutationError(null);
    try { await updateAdminRole(name, input); refresh(); return true; }
    catch (error: unknown) { setMutationError(normalizeError(error, "Unable to update this Atlas role.")); return false; }
    finally { setBusyKey(null); }
  }, [refresh]);

  const removeRole = useCallback(async (name: string): Promise<boolean> => {
    setBusyKey(`role:${name}`); setMutationError(null);
    try { await deleteAdminRole(name); refresh(); return true; }
    catch (error: unknown) { setMutationError(normalizeError(error, "Unable to delete this Atlas role.")); return false; }
    finally { setBusyKey(null); }
  }, [refresh]);

  return { state, refresh, mutationError, busyKey, createRole, updateRole, removeRole };
}
