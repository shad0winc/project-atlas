"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";

import type { AtlasLoginRequest } from "../api/contracts";
import { readCurrentAtlasUser } from "../services/auth";
import {
  loginBrowserSession,
  logoutBrowserSession,
  refreshBrowserIdentity,
  restoreBrowserSession
} from "../services/browser-auth";

import { registerAtlasAuthLifecycle } from "./session-lifecycle";
import { clearAtlasAuthSession, readAtlasAuthSession, writeAtlasAuthSession } from "./storage";
import { type AtlasAuthContextValue, type AtlasAuthSession, type AtlasAuthStatus } from "./types";

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
    initialSession() ? "authenticated" : "loading"
  );

  const generation = useRef(0);

  useEffect(() => {
    if (readAtlasAuthSession() !== null) return;
    let disposed = false;
    const expected = generation.current;
    void restoreBrowserSession()
      .then((restored) => {
        if (disposed || generation.current !== expected) return;
        writeAtlasAuthSession(restored);
        setSession(restored);
        setStatus("authenticated");
      })
      .catch(() => {
        if (disposed || generation.current !== expected) return;
        clearAtlasAuthSession();
        setSession(null);
        setStatus("unauthenticated");
      });
    return () => {
      disposed = true;
    };
  }, []);

  const login = useCallback(async (credentials: AtlasLoginRequest): Promise<void> => {
    const expected = ++generation.current;
    clearAtlasAuthSession();
    setSession(null);
    setStatus("loading");

    try {
      const tokens = await loginBrowserSession(credentials);
      const user = await readCurrentAtlasUser(tokens.accessToken);
      if (generation.current !== expected) return;

      const nextSession: AtlasAuthSession = {
        tokens,
        user
      };

      writeAtlasAuthSession(nextSession);
      setSession(nextSession);
      setStatus("authenticated");
    } catch (error: unknown) {
      if (generation.current !== expected) throw error;
      clearAtlasAuthSession();
      setSession(null);
      setStatus("unauthenticated");
      throw error;
    }
  }, []);

  const expireSession = useCallback((): void => {
    generation.current += 1;
    clearAtlasAuthSession();
    setSession(null);
    setStatus("unauthenticated");
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    generation.current += 1;
    // Confirm server revocation before reporting logout. A network failure
    // leaves the current page signed in so the user can retry explicitly.
    await logoutBrowserSession();
    expireSession();
  }, [expireSession]);

  const refreshAccessToken = useCallback(async (): Promise<string> => {
    const currentSession = readAtlasAuthSession();

    if (currentSession === null) {
      throw new Error("Atlas authentication session is unavailable.");
    }

    const expected = generation.current;
    const nextSession = await refreshBrowserIdentity(currentSession);
    if (generation.current !== expected) {
      throw new Error("Atlas session changed while refreshing.");
    }

    writeAtlasAuthSession(nextSession);
    setSession(nextSession);
    setStatus("authenticated");

    return nextSession.tokens.accessToken;
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
