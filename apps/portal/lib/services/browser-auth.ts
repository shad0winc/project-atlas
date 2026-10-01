import { atlasApiRequest } from "../api/client";
import type { AtlasLoginRequest, AtlasCurrentUserResponse } from "../api/contracts";
import type { AtlasAuthSession, AtlasAuthTokens } from "../auth/types";
async function readBrowserUser(accessToken: string): Promise<AtlasCurrentUserResponse> {
  // Identity validation is itself part of restoration/rotation. A 401 here
  // must not recursively join the rotation promise currently awaiting it.
  return atlasApiRequest<AtlasCurrentUserResponse>("/auth/me", {
    accessToken,
    cache: "no-store",
    retryAuthentication: false
  });
}

interface BrowserTokenResponse {
  readonly access_token: string;
  readonly token_type: string;
}

// Serialize cookie rotation across tabs. Without Web Locks, fail visibly rather
// than silently exposing a refresh token or racing its single-use rotation.
async function browserSessionRequest<T>(action: string, body?: unknown): Promise<T> {
  if (typeof navigator === "undefined" || !navigator.locks) {
    throw new Error("This browser does not support secure Atlas session coordination.");
  }
  return navigator.locks.request("atlas-browser-session", async () =>
    atlasApiRequest<T>(`/auth/browser/${action}`, {
      method: "POST",
      body,
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Atlas-Browser-Session": "1" },
      retryAuthentication: false
    })
  );
}

function browserTokens(response: BrowserTokenResponse): AtlasAuthTokens {
  const accessToken = response.access_token.trim();
  const tokenType = response.token_type.trim();
  if (!accessToken || tokenType.toLowerCase() !== "bearer") {
    throw new Error("Atlas returned invalid browser-session credentials.");
  }
  // No refresh credential is returned to JavaScript. This field remains empty
  // for compatibility with the shared in-memory session interface.
  return { accessToken, tokenType, refreshToken: "" };
}

export async function loginBrowserSession(
  credentials: AtlasLoginRequest
): Promise<AtlasAuthTokens> {
  return browserTokens(await browserSessionRequest<BrowserTokenResponse>("login", credentials));
}

export async function refreshBrowserSession(): Promise<AtlasAuthTokens> {
  return browserTokens(await browserSessionRequest<BrowserTokenResponse>("refresh"));
}

export async function logoutBrowserSession(): Promise<void> {
  await browserSessionRequest<void>("logout");
}

let restoring: Promise<AtlasAuthSession> | null = null;
export function restoreBrowserSession(): Promise<AtlasAuthSession> {
  // React Strict Mode can initialize the provider twice. Share only the pending
  // restoration; never cache an authenticated identity after it completes.
  if (restoring !== null) return restoring;
  const pending = refreshBrowserSession().then(async (tokens) => ({
    tokens,
    user: await readBrowserUser(tokens.accessToken)
  }));
  restoring = pending;
  void pending
    .finally(() => {
      if (restoring === pending) restoring = null;
    })
    .catch(() => {});
  return pending;
}

export async function refreshBrowserIdentity(current: AtlasAuthSession): Promise<AtlasAuthSession> {
  const tokens = await refreshBrowserSession();
  const user = await readBrowserUser(tokens.accessToken);
  if (user.user_id !== current.user.user_id) {
    throw new Error("Atlas account changed in another tab. Sign in again.");
  }
  return { tokens, user };
}
