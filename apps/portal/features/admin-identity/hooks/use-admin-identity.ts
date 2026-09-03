"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../../lib/auth/use-auth";
import {
  createAdminInvitation,
  createAdminUser,
  loadAdminInvitations,
  loadAdminUser,
  loadAdminUsers,
  revokeAdminInvitation,
  setAdminUserPassword,
  updateAdminUser,
  type AdminInvitation,
  type AdminUser,
  type AdminUserCreateInput,
  type AdminUserUpdateInput,
  type InvitationCreateInput
} from "../api/admin-identity";

export type AdminIdentityState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "error"; error: Error }>
  | Readonly<{ status: "ready"; users: readonly AdminUser[]; invitations: readonly AdminInvitation[] }>;

function normalizeError(value: unknown, fallback: string): Error { return value instanceof Error ? value : new Error(fallback); }

export function useAdminIdentity() {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState<AdminIdentityState>({ status: "loading" });
  const [requestVersion, setRequestVersion] = useState(0);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [mutationError, setMutationError] = useState<Error | null>(null);
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const refresh = useCallback(() => { setState({ status: "loading" }); setMutationError(null); setRequestVersion((v) => v + 1); }, []);

  useEffect(() => {
    const controller = new AbortController();
    if (!isAuthenticated) return () => controller.abort();
    Promise.all([loadAdminUsers(controller.signal), loadAdminInvitations(controller.signal)])
      .then(([users, invitations]) => { if (!controller.signal.aborted) setState({ status: "ready", users, invitations }); })
      .catch((error: unknown) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return;
        setState({ status: "error", error: normalizeError(error, "Unable to load Atlas Administrator identity data.") });
      });
    return () => controller.abort();
  }, [isAuthenticated, requestVersion]);

  const inspectUser = useCallback(async (identifier: string) => {
    setDetailLoading(true); setMutationError(null);
    try { setSelectedUser(await loadAdminUser(identifier)); }
    catch (error: unknown) { setMutationError(normalizeError(error, "Unable to load this Atlas user.")); }
    finally { setDetailLoading(false); }
  }, []);

  const createUser = useCallback(async (input: AdminUserCreateInput): Promise<boolean> => {
    setBusyKey("user:create");
    setMutationError(null);

    try {
      const created = await createAdminUser(input);

      setSelectedUser(created);
      setState((current) =>
        current.status !== "ready"
          ? current
          : {
              ...current,
              users: [
                created,
                ...current.users.filter((user) => user.userId !== created.userId)
              ]
            }
      );

      return true;
    } catch (error: unknown) {
      setMutationError(
        normalizeError(error, "Unable to create this Atlas user.")
      );
      return false;
    } finally {
      setBusyKey(null);
    }
  }, []);

  const mutateUser = useCallback(
    async (
      identifier: string,
      updates: AdminUserUpdateInput
    ): Promise<boolean> => {
      setBusyKey(`user:${identifier}`);
      setMutationError(null);

      try {
        const updated = await updateAdminUser(
          identifier,
          updates
        );

        setSelectedUser((current) =>
          current?.userId === updated.userId
            ? updated
            : current
        );

        setState((current) =>
          current.status !== "ready"
            ? current
            : {
                ...current,
                users: current.users.map((user) =>
                  user.userId === updated.userId
                    ? updated
                    : user
                )
              }
        );

        return true;
      } catch (error: unknown) {
        setMutationError(
          normalizeError(
            error,
            "Unable to update this Atlas user."
          )
        );
        return false;
      } finally {
        setBusyKey(null);
      }
    },
    []
  );

  const setUserPassword = useCallback(
    async (
      identifier: string,
      newPassword: string
    ): Promise<boolean> => {
      setBusyKey(`user-password:${identifier}`);
      setMutationError(null);

      try {
        await setAdminUserPassword(
          identifier,
          newPassword
        );
        return true;
      } catch (error: unknown) {
        setMutationError(
          normalizeError(
            error,
            "Unable to set this Atlas user's password."
          )
        );
        return false;
      } finally {
        setBusyKey(null);
      }
    },
    []
  );

  const createInvitation = useCallback(async (input: InvitationCreateInput): Promise<boolean> => {
    setBusyKey("invitation:create"); setMutationError(null); setCreatedToken(null);
    try {
      const created = await createAdminInvitation(input);
      setCreatedToken(created.token ?? null);
      setState((current) => current.status !== "ready" ? current : { ...current, invitations: [created, ...current.invitations.filter((i) => i.inviteId !== created.inviteId)] });
      return true;
    } catch (error: unknown) { setMutationError(normalizeError(error, "Unable to create the invitation.")); return false; }
    finally { setBusyKey(null); }
  }, []);

  const revokeInvitation = useCallback(async (inviteId: string): Promise<boolean> => {
    setBusyKey(`invitation:${inviteId}`); setMutationError(null);
    try {
      const revoked = await revokeAdminInvitation(inviteId);
      setState((current) => current.status !== "ready" ? current : { ...current, invitations: current.invitations.map((i) => i.inviteId === revoked.inviteId ? revoked : i) });
      return true;
    } catch (error: unknown) { setMutationError(normalizeError(error, "Unable to revoke the invitation.")); return false; }
    finally { setBusyKey(null); }
  }, []);

  return { state, refresh, selectedUser, detailLoading, inspectUser, clearSelectedUser: () => setSelectedUser(null),
    createUser,
    mutateUser,
    setUserPassword,
    createInvitation,
    revokeInvitation,
    mutationError,
    createdToken,
    clearCreatedToken: () => setCreatedToken(null),
    busyKey
  };
}
