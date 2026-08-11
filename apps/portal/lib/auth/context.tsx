"use client";

import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import type { AtlasLoginRequest } from "../api/contracts";
import {
  loginAtlasUser,
  logoutAtlasSession,
  readCurrentAtlasUser,
  refreshAtlasTokens
} from "../services/auth";

import { registerAtlasAuthLifecycle } from "./session-lifecycle";
import { clearAtlasAuthSession, readAtlasAuthSession, writeAtlasAuthSession } from "./storage";
import {
  normalizeAtlasAuthTokens,
  type AtlasAuthContextValue,
  type AtlasAuthSession,
  type AtlasAuthStatus
} from "./types";

export const AtlasAuthContext = createContext<AtlasAuthContextValue | null>(null);

type AuthProviderProps = Readonly<{
  children: ReactNode;
}>;

function initialSession(): AtlasAuthSession | null {
  return readAtlasAuthSession();
}

export function AuthProvider({ children }: AuthProviderProps): React.ReactElement {
  const [session, setSession] = useState<AtlasAuthSession | null>(initialSession);

  const [status, setStatus] = useState<AtlasAuthStatus>(() =>
    initialSession() ? "authenticated" : "unauthenticated"
  );

  const login = useCallback(async (credentials: AtlasLoginRequest): Promise<void> => {
    setStatus("loading");

    try {
      const tokenResponse = await loginAtlasUser(credentials);
      const tokens = normalizeAtlasAuthTokens(tokenResponse);
      const user = await readCurrentAtlasUser(tokens.accessToken);

      const nextSession: AtlasAuthSession = {
        tokens,
        user
      };

      writeAtlasAuthSession(nextSession);
      setSession(nextSession);
      setStatus("authenticated");
    } catch (error: unknown) {
      clearAtlasAuthSession();
      setSession(null);
      setStatus("unauthenticated");
      throw error;
    }
  }, []);

  const expireSession = useCallback((): void => {
    clearAtlasAuthSession();
    setSession(null);
    setStatus("unauthenticated");
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    const currentSession = readAtlasAuthSession();

    try {
      if (currentSession !== null) {
        await logoutAtlasSession(currentSession.tokens.refreshToken);
      }
    } catch {
      // Explicit sign-out must still clear local credentials if revocation
      // cannot reach the API. The server session will expire independently.
    } finally {
      expireSession();
    }
  }, [expireSession]);

  const refreshAccessToken = useCallback(async (): Promise<string> => {
    const currentSession = readAtlasAuthSession();

    if (currentSession === null) {
      throw new Error("Atlas authentication session is unavailable.");
    }

    const tokenResponse = await refreshAtlasTokens(currentSession.tokens.refreshToken);

    const tokens = normalizeAtlasAuthTokens(tokenResponse);

    const nextSession: AtlasAuthSession = {
      ...currentSession,
      tokens
    };

    writeAtlasAuthSession(nextSession);
    setSession(nextSession);
    setStatus("authenticated");

    return tokens.accessToken;
  }, []);

  useEffect(() => {
    return registerAtlasAuthLifecycle({
      refreshAccessToken,
      expireSession
    });
  }, [expireSession, refreshAccessToken]);

  const value = useMemo<AtlasAuthContextValue>(
    () => ({
      status,
      session,
      user: session?.user ?? null,
      isAuthenticated: status === "authenticated" && session !== null,
      login,
      logout
    }),
    [login, logout, session, status]
  );

  return <AtlasAuthContext.Provider value={value}>{children}</AtlasAuthContext.Provider>;
}
