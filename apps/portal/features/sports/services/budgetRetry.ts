import { AtlasApiError } from "../../../lib/api/errors";

type Dependencies = Readonly<{
  now?: () => number;
  wait?: (milliseconds: number, signal: AbortSignal) => Promise<void>;
}>;

function waitForBudget(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason ?? new DOMException("Sports request cancelled.", "AbortError"));
      return;
    }
    const cancelled = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", cancelled);
      reject(signal.reason ?? new DOMException("Sports request cancelled.", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", cancelled);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", cancelled, { once: true });
  });
}

type RetryLimits = Readonly<{ attempts: number; waitMs: number; deadlineMs: number }>;
const interactiveLimits: RetryLimits = { attempts: 3, waitMs: 20_000, deadlineMs: 30_000 };
const scheduleLimits: RetryLimits = { attempts: 12, waitMs: 90_000, deadlineMs: 120_000 };

/** Searches retain their short, cancellable retry window. */
export function withSportsBudgetRetry<T>(
  task: (signal: AbortSignal) => Promise<T>,
  options: Readonly<{ signal?: AbortSignal }> = {},
  dependencies: Dependencies = {},
): Promise<T> {
  return withBudgetRetry(task, options, dependencies, interactiveLimits);
}

/** Multi-league cold schedules reuse cached dates while respecting Retry-After. */
export function withSportsScheduleBudgetRetry<T>(
  task: (signal: AbortSignal) => Promise<T>,
  options: Readonly<{ signal?: AbortSignal }> = {},
  dependencies: Dependencies = {},
): Promise<T> {
  return withBudgetRetry(task, options, dependencies, scheduleLimits);
}

async function withBudgetRetry<T>(
  task: (signal: AbortSignal) => Promise<T>,
  options: Readonly<{ signal?: AbortSignal }> = {},
  dependencies: Dependencies,
  limits: RetryLimits,
): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort(options.signal?.reason);
  options.signal?.addEventListener("abort", cancel, { once: true });
  if (options.signal?.aborted) cancel();
  const deadlineTimer = setTimeout(
    () => controller.abort(new DOMException("Sports request timed out.", "TimeoutError")),
    limits.deadlineMs,
  );
  const now = dependencies.now ?? Date.now;
  const wait = dependencies.wait ?? waitForBudget;
  const started = now();
  let waited = 0;
  try {
    for (let attempt = 0; ; attempt += 1) {
      controller.signal.throwIfAborted();
      try {
        return await task(controller.signal);
      } catch (error) {
        if (controller.signal.aborted) throw controller.signal.reason;
        if (!(error instanceof AtlasApiError) || error.status !== 429 || attempt >= limits.attempts - 1) throw error;
        const seconds = error.retryAfterSeconds;
        if (seconds === null || !Number.isFinite(seconds) || seconds < 0) throw error;
        const milliseconds = Math.max(1, seconds) * 1000;
        if (waited + milliseconds > limits.waitMs || now() - started + milliseconds >= limits.deadlineMs) throw error;
        waited += milliseconds;
        await wait(milliseconds, controller.signal);
      }
    }
  } finally {
    clearTimeout(deadlineTimer);
    options.signal?.removeEventListener("abort", cancel);
  }
}
