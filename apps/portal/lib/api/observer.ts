/**
 * Optional lifecycle observation contracts for Atlas Portal API requests.
 *
 * Observers are intended for logging, metrics, tracing, and diagnostics.
 * They must not alter request behavior or response values.
 */

export interface AtlasApiRequestObservation {
  readonly requestId: string;
  readonly method: string;
  readonly path: string;
  readonly startedAt: number;
}

export interface AtlasApiResponseObservation extends AtlasApiRequestObservation {
  readonly completedAt: number;
  readonly durationMs: number;
  readonly status: number;
}

export interface AtlasApiErrorObservation extends AtlasApiRequestObservation {
  readonly completedAt: number;
  readonly durationMs: number;
  readonly error: unknown;
  readonly status?: number;
}

export interface AtlasApiObserver {
  readonly onRequest?: (observation: AtlasApiRequestObservation) => void;
  readonly onResponse?: (observation: AtlasApiResponseObservation) => void;
  readonly onError?: (observation: AtlasApiErrorObservation) => void;
}

export function notifyAtlasApiObservers<TObservation>(
  observers: readonly AtlasApiObserver[] | undefined,
  selectCallback: (observer: AtlasApiObserver) => ((observation: TObservation) => void) | undefined,
  observation: TObservation
): void {
  if (!observers?.length) {
    return;
  }

  for (const observer of observers) {
    try {
      selectCallback(observer)?.(observation);
    } catch {
      // Observability must never alter API request behavior.
    }
  }
}
