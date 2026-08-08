/**
 * Process-local authentication lifecycle coordination.
 *
 * The Portal keeps authentication tokens in memory. This coordinator allows
 * the API client to request token rotation without depending on React while
 * preserving a single refresh operation across concurrent requests.
 */

export interface AtlasAuthLifecycle {
  readonly refreshAccessToken: () => Promise<string>;
  readonly expireSession: () => void;
}

export interface AtlasAuthLifecycleObserver {
  readonly onRefreshStarted?: () => void;
  readonly onRefreshSucceeded?: () => void;
  readonly onRefreshFailed?: (error: unknown) => void;
  readonly onSessionExpired?: () => void;
}

let activeLifecycle: AtlasAuthLifecycle | null = null;
let activeRefresh: Promise<string> | null = null;

const observers = new Set<AtlasAuthLifecycleObserver>();

function notifyObservers(
  selectCallback: (
    observer: AtlasAuthLifecycleObserver
  ) => ((...arguments_: never[]) => void) | undefined,
  ...arguments_: never[]
): void {
  for (const observer of observers) {
    try {
      selectCallback(observer)?.(...arguments_);
    } catch {
      // Authentication observability must never alter session behavior.
    }
  }
}

export function registerAtlasAuthLifecycle(lifecycle: AtlasAuthLifecycle): () => void {
  activeLifecycle = lifecycle;

  return (): void => {
    if (activeLifecycle === lifecycle) {
      activeLifecycle = null;
      activeRefresh = null;
    }
  };
}

export function subscribeAtlasAuthLifecycle(observer: AtlasAuthLifecycleObserver): () => void {
  observers.add(observer);

  return (): void => {
    observers.delete(observer);
  };
}

export function canRefreshAtlasAuthSession(): boolean {
  return activeLifecycle !== null;
}

export function expireAtlasAuthSession(): void {
  const lifecycle = activeLifecycle;

  if (lifecycle === null) {
    return;
  }

  lifecycle.expireSession();

  notifyObservers((observer) => observer.onSessionExpired);
}

export async function refreshAtlasAuthAccessToken(): Promise<string> {
  if (activeRefresh !== null) {
    return activeRefresh;
  }

  const lifecycle = activeLifecycle;

  if (lifecycle === null) {
    throw new Error("Atlas authentication lifecycle is not registered.");
  }

  notifyObservers((observer) => observer.onRefreshStarted);

  activeRefresh = lifecycle
    .refreshAccessToken()
    .then((accessToken) => {
      const normalizedToken = accessToken.trim();

      if (!normalizedToken) {
        throw new Error("Refreshed Atlas access token cannot be empty.");
      }

      notifyObservers((observer) => observer.onRefreshSucceeded);

      return normalizedToken;
    })
    .catch((error: unknown) => {
      notifyObservers(
        (observer) => observer.onRefreshFailed as ((...arguments_: never[]) => void) | undefined,
        error as never
      );

      lifecycle.expireSession();
      notifyObservers((observer) => observer.onSessionExpired);

      throw error;
    })
    .finally(() => {
      activeRefresh = null;
    });

  return activeRefresh;
}

/**
 * Test-only reset for process-local lifecycle state.
 */
export function resetAtlasAuthLifecycleForTests(): void {
  activeLifecycle = null;
  activeRefresh = null;
  observers.clear();
}
