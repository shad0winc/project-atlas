"use client";

import { createContext, useCallback, useMemo, useState, type ReactNode } from "react";

import type { AtlasLoginRequest } from "../api/contracts";
import { loginAtlasUser, readCurrentAtlasUser } from "../services/auth";

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

  const logout = useCallback((): void => {
    clearAtlasAuthSession();
    setSession(null);
    setStatus("unauthenticated");
  }, []);

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
